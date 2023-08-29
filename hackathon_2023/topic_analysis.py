import re
import string

import spacy
import nltk
from nltk.corpus import stopwords
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from gensim import corpora
from gensim.models import LdaModel, Phrases

nltk.download('stopwords')
nlp = spacy.load("en_core_web_md")  # `poetry add {download link}` from https://spacy.io/models/en#en_core_web_md


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
    translator = str.maketrans('', '', string.punctuation)
    cleaned_messages = [message.translate(translator) for message in messages]

    # Tokenize the messages, filter out stop words and short words
    tokenized_messages = [[word for word in message.split() if word not in stop_words and len(word) > 3] for message in
                          cleaned_messages]

    # Create n-gram models
    bi_gram = Phrases(tokenized_messages, min_count=5, threshold=100)
    tri_gram = Phrases(bi_gram[tokenized_messages], threshold=100)
    tokenized_messages = [tri_gram[bi_gram[message]] for message in tokenized_messages]

    # Create a dictionary and corpus for LDA
    dictionary = corpora.Dictionary(tokenized_messages)
    dictionary.filter_extremes(no_below=5, no_above=0.5)
    corpus = [dictionary.doc2bow(message) for message in tokenized_messages]

    # Train the LDA model
    lda_model = LdaModel(corpus, num_topics=num_topics, id2word=dictionary, passes=20)  # was 15

    # Extract topics
    topics = {}
    for i in range(num_topics):
        topics[i] = [word[0] for word in lda_model.show_topic(i, topn=5)]
    return topics


async def analyze_topics_of_history(channel_name: str, messages, num_topics: int = 7) -> str:
    # Remove URLs
    messages = [re.sub(r'http\S+', '', message) for message in messages]

    # Remove emojis
    messages = [re.sub(r':[^:\s]+:', '', message) for message in messages]

    # Lemmatize e.g. running -> run
    messages = [' '.join([token.lemma_ for token in nlp(message)]) for message in messages]

    # Define stop words
    stop_words = set(stopwords.words('english'))
    for word in [channel_name, 'join', 'late', 'channel', 'team', 'like']:  # context-specific stop words
        stop_words.add(word)

    vectorizer = TfidfVectorizer(stop_words=list(stop_words), max_df=0.85, max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(messages)
    terms = vectorizer.get_feature_names_out()

    kmeans_results = await _kmeans_topics(tfidf_matrix, num_topics, terms)
    lsa_results = await _lsa_topics(tfidf_matrix, num_topics, terms)
    lda_results = await _lda_topics(messages, num_topics, stop_words)

    topics_str = f"*Topic Analysis of #{channel_name}:*\n\n"

    for (name, model) in [('KMeans', kmeans_results), ('LSA', lsa_results), ('LDA (w/ Gensim)', lda_results)]:
        topics_str += f"\n*{name} Results:*\n"
        for topic, terms in model.items():
            topics_str += f" • {', '.join(terms)}\n"

    print(topics_str)

    # -- GPT-4 Prompt for Synthesis --

    # For the provided results from topic analyses on the entire history of the "product_leadership" Slack channel,
    # please provide a conversational summary and interpretation. Each bullet is a cluster under the methodology
    # heading; do not mention the methodology. When analyzing each cluster, please conflate duplicates and ignore
    # meaningless clusters. Do not include this prompt in your response. Please provide a direct bullet-point
    # analysis of the provided results. Avoid introductory or transitional sentences. Focus directly on the content.
    # Please do not split up your response based on the analysis methodology; you should give one set of takeaways.
    # \n\n{topics_str}

    return topics_str
