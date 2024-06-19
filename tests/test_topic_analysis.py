import pytest
import re

from unittest.mock import patch, MagicMock

from ossai import topic_analysis


# Fixtures
@pytest.fixture
def messages():
    corpus = """    
In the animated universe of "Futurama," scientific progress leaps beyond the bounds of contemporary imagination, 
introducing viewers to a world where space travel and time manipulation are everyday occurrences. The series, 
set in the 31st century, follows the adventures of a hapless delivery boy, Philip J. Fry, who is cryogenically frozen 
and wakes up a thousand years later. Alongside Fry, a diverse cast of characters, including a one-eyed pilot, 
a robot with a penchant for bending rules, and a lobster-like scientist, explore the galaxy, encountering bizarre 
alien species and grappling with the paradoxes of time travel. "Futurama" cleverly blends humor with scientific and 
philosophical questions, challenging audiences to consider the impact of technology on society and the human 
condition."""

    corpus = corpus.replace('\n', '')
    # split `corpus` into an array of sentences, then split each sentence into an array of words
    # structured as a Message object
    return [message.strip() for message in corpus.split('.')[:-1]]


@pytest.fixture
def num_topics():
    return 3


@pytest.fixture
def terms():
    return ['term1', 'term2', 'term3']


@pytest.fixture
def tfidf_matrix():
    return [[1, 2, 3], [4, 5, 6], [7, 8, 9]]


@pytest.fixture
def stop_words():
    return {'a', 'an', 'the', 'Futurama'}


# Tests
@pytest.mark.asyncio
async def test_kmeans_topics(tfidf_matrix, num_topics, terms):
    result = await topic_analysis._kmeans_topics(tfidf_matrix, num_topics, terms)
    assert isinstance(result, dict)
    assert len(result) == num_topics


@pytest.mark.asyncio
async def test_lsa_topics(tfidf_matrix, num_topics, terms):
    result = await topic_analysis._lsa_topics(tfidf_matrix, num_topics, terms)
    assert isinstance(result, dict)
    assert len(result) == num_topics


@pytest.mark.asyncio
async def test_lda_topics(messages, num_topics, stop_words):
    result = await topic_analysis._lda_topics(messages, num_topics, stop_words)
    assert isinstance(result, dict)
    assert len(result) == num_topics


@pytest.mark.asyncio
async def test_synthesize_topics(monkeypatch):
    # Setup test data
    topics_str = "KMeans Results:\n - term1, term2, term3\nLSA Results:\n - term4, term5, term1"
    channel = "test_channel"
    user = {"name": "testuser", "title": "developer"}
    is_private = False

    # Mocking ChatOpenAI and StrOutputParser
    class MockChatOpenAI:
        def __init__(self, model, temperature):
            pass

        def __call__(self, *args, **kwargs):
            return "Mocked response from ChatOpenAI"

    class MockStrOutputParser:
        def __call__(self, *args, **kwargs):
            return "- term1, term2, term3\n- term4, term5, term1"

    # Patching the dependencies
    monkeypatch.setattr(topic_analysis, "ChatOpenAI", MockChatOpenAI)
    monkeypatch.setattr(topic_analysis, "StrOutputParser", MockStrOutputParser)

    # Call the function
    (result, run_id) = await topic_analysis._synthesize_topics(topics_str, channel, user, is_private)

    # Assertions
    assert result == "- term1, term2, term3\n- term4, term5, term1"
    assert isinstance(run_id, str)
    assert re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', run_id) is not None



@patch('ossai.topic_analysis._synthesize_topics')
@patch('ossai.topic_analysis._lda_topics')
@patch('ossai.topic_analysis._lsa_topics')
@patch('ossai.topic_analysis._kmeans_topics')
@pytest.mark.asyncio
async def test_analyze_topics_of_history(mock_kmeans, mock_lsa, mock_lda, mock_synthesize, messages, num_topics):
    mock_kmeans.return_value = {'topic1': ['term1', 'term2', 'term3']}
    mock_lsa.return_value = {'topic2': ['term4', 'term5', 'term1']}
    mock_lda.return_value = {'topic3': ['term1', 'term6', 'term7']}
    mock_synthesize.return_value = 'synthesized topics'
    result = await topic_analysis.analyze_topics_of_history('channel_name', messages, num_topics)
    assert isinstance(result, str)
