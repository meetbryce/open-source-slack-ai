import os
import re
import string
import nltk
import spacy

from uuid import UUID
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from gensim import corpora
from gensim.models import LdaModel, Phrases
from nltk.corpus import stopwords
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from ossai.utils import get_llm_config, get_langsmith_config
from ossai.logging_config import logger

load_dotenv(override=True)
nltk.download("stopwords")
try:
    nlp = spacy.load(
        "en_core_web_md"
    )  # `poetry add {download link}` from https://spacy.io/models/en#en_core_web_md
except:
    logger.warning(
        "Downloading language model for the spaCy POS tagger (don't worry, this will only happen once)"
    )
    from spacy.cli import download

    download("en_core_web_md")
    nlp = spacy.load("en_core_web_md")
config = get_llm_config()
TEMPERATURE = (
    float(config["temperature"]) + 0.1
)  # a little more creativity is beneficial here
DEBUG = bool(os.environ.get("DEBUG", False))


async def _kmeans_topics(tfidf_matrix, num_topics, terms):
    km = KMeans(n_clusters=num_topics)
    km.fit(tfidf_matrix)
    order_centroids = km.cluster_centers_.argsort()[:, ::-1]
    cluster_terms = {}
    for i in range(num_topics):
        cluster_terms[i] = [terms[ind] for ind in order_centroids[i, :5]]
    return cluster_terms


async def _lsa_topics(tfidf_matrix, num_topics, terms):
    lsa_model = TruncatedSVD(n_components=num_topics)
    lsa_model.fit_transform(tfidf_matrix)
    topics = {}
    for i, topic in enumerate(lsa_model.components_):
        topics[i] = [terms[t] for t in topic.argsort()[:-6:-1]]
    return topics


async def _lda_topics(messages, num_topics, stop_words):
    # Remove punctuation
    translator = str.maketrans("", "", string.punctuation)
    cleaned_messages = [message.translate(translator) for message in messages]

    # Tokenize the messages, filter out stop words and short words
    tokenized_messages = [
        [word for word in message.split() if word not in stop_words and len(word) > 3]
        for message in cleaned_messages
    ]

    # Create n-gram models
    bi_gram = Phrases(tokenized_messages, min_count=5, threshold=100)
    tri_gram = Phrases(bi_gram[tokenized_messages], threshold=100)
    tokenized_messages = [tri_gram[bi_gram[message]] for message in tokenized_messages]

    # Create a dictionary and corpus for LDA
    dictionary = corpora.Dictionary(tokenized_messages)
    dictionary.filter_extremes(no_below=2, no_above=0.9)
    corpus = [dictionary.doc2bow(message) for message in tokenized_messages]

    # Train the LDA model
    lda_model = LdaModel(
        corpus, num_topics=num_topics, id2word=dictionary, passes=20
    )  # was 15

    # Extract topics
    topics = {}
    for i in range(num_topics):
        topics[i] = [word[0] for word in lda_model.show_topic(i, topn=5)]
    return topics


async def _synthesize_topics(
    topics_str: str, channel: str, user: str, is_private: bool = False
) -> tuple[str, UUID]:
    system_msg = """\
    You are a topic analysis expert, synthesizing the results of various topic analysis methods conducted on a Slack channel's message history. 
    You write conversationally and never use technical terms like KMeans, LDA, clustering, or LSA. 
    You always respond in markdown formatting ready for Slack. Use - for bullets, not *.
    Do not wrap your response in code blocks or markdown code blocks.
    """

    user_msg = f"""\
    For the provided results from topic analyses on the entire history of the "{channel}" Slack channel, 
    please provide a conversational summary and interpretation. Each bullet is a cluster under the methodology 
    heading; do not mention the methodology. When analyzing each cluster, please conflate duplicates and ignore 
    meaningless clusters. Do not include this prompt in your response. Please provide a direct bullet-point 
    analysis of the provided results. Avoid introductory or transitional sentences. Focus directly on the 
    content. Please do not split up your response based on the analysis methodology; you should give one set of 
    takeaways.

    {topics_str}
    """

    config = get_llm_config()
    model = ChatOpenAI(model=config["chat_model"], temperature=config["temperature"])

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_msg), ("user", user_msg)]
    )

    parser = StrOutputParser()
    chain = prompt_template | model | parser  # todo: add privacy mode

    langsmith_config = get_langsmith_config(
        feature_name="channel_topics",
        user=user,
        channel=channel,
        is_private=is_private,
    )
    logger.debug(f"{langsmith_config=}")
    result = chain.invoke(
        {"topics_str": topics_str, "channel": channel}, config=langsmith_config
    )
    logger.debug(result)

    # parse the message reformat it for delivery via Slack message
    result = result.replace("\n* ", "\n- ")
    result = result.replace("**", "*")

    return result, langsmith_config["run_id"]


async def analyze_topics_of_history(
    channel_name: str,
    messages,
    user: str,
    num_topics: int = 6,
    is_private: bool = False,
) -> str:
    # Remove URLs
    messages = [re.sub(r"http\S+", "", message) for message in messages]

    # Remove emojis
    messages = [re.sub(r":[^:\s]+:", "", message) for message in messages]

    # Lemmatize e.g. running -> run
    messages = [
        " ".join([token.lemma_ for token in nlp(message)]) for message in messages
    ]

    # todo: Support the ability to redact the names of channel members (to prevent any awkwardness)

    # Define stop words
    stop_words = set(stopwords.words("english"))
    for word in [
        channel_name,
        "join",
        "late",
        "channel",
        "team",
        "like",
    ]:  # context-specific stop words
        stop_words.add(word)

    vectorizer = TfidfVectorizer(
        stop_words=list(stop_words), max_df=0.85, max_features=5000
    )
    tfidf_matrix = vectorizer.fit_transform(messages)
    terms = vectorizer.get_feature_names_out()

    # todo: make these part of the langsmith trace
    kmeans_results = await _kmeans_topics(tfidf_matrix, num_topics, terms)
    lsa_results = await _lsa_topics(tfidf_matrix, num_topics, terms)
    lda_results = await _lda_topics(messages, num_topics, stop_words)

    topics_str = f""

    for name, model in [
        ("KMeans", kmeans_results),
        ("LSA", lsa_results),
        ("LDA (w/ Gensim)", lda_results),
    ]:
        if DEBUG:
            topics_str += f"\n*{name} Results:*\n"
        for topic, terms in model.items():
            topics_str += f" • {', '.join(terms)}\n"

    logger.debug(topics_str)

    return await _synthesize_topics(topics_str, channel_name, user, is_private)
