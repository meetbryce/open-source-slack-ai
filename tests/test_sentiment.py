import pytest
from unittest.mock import patch, MagicMock
from ossai.sentiment import get_traditional_sentiment, _get_analyzer


class TestSentiment:
    def test_positive_sentiment(self):
        """Test that positive text returns positive sentiment scores"""
        text = "I love this! It's absolutely wonderful and amazing!"
        result = get_traditional_sentiment(text)
        
        assert isinstance(result, dict)
        assert all(key in result for key in ['neg', 'neu', 'pos', 'compound'])
        assert result['pos'] > result['neg']
        assert result['compound'] > 0

    def test_negative_sentiment(self):
        """Test that negative text returns negative sentiment scores"""
        text = "This is terrible! I hate it and it's completely awful!"
        result = get_traditional_sentiment(text)
        
        assert isinstance(result, dict)
        assert all(key in result for key in ['neg', 'neu', 'pos', 'compound'])
        assert result['neg'] > result['pos']
        assert result['compound'] < 0

    def test_neutral_sentiment(self):
        """Test that neutral text returns balanced sentiment scores"""
        text = "The meeting is scheduled for 3 PM in conference room A."
        result = get_traditional_sentiment(text)
        
        assert isinstance(result, dict)
        assert all(key in result for key in ['neg', 'neu', 'pos', 'compound'])
        assert result['neu'] > result['pos']
        assert result['neu'] > result['neg']

    def test_empty_text(self):
        """Test that empty or whitespace text returns neutral scores"""
        for text in ["", "   ", "\n\t", None]:
            if text is None:
                continue  # Skip None as it would cause an error
            result = get_traditional_sentiment(text)
            
            assert isinstance(result, dict)
            assert result['neg'] == 0.0
            assert result['neu'] == 1.0
            assert result['pos'] == 0.0
            assert result['compound'] == 0.0

    def test_mixed_sentiment(self):
        """Test text with mixed sentiment"""
        text = "I love the interface, but I hate the slow loading times."
        result = get_traditional_sentiment(text)
        
        assert isinstance(result, dict)
        assert all(key in result for key in ['neg', 'neu', 'pos', 'compound'])
        # Mixed sentiment should have both positive and negative components
        assert result['pos'] > 0
        assert result['neg'] > 0

    def test_score_ranges(self):
        """Test that all scores are within expected ranges"""
        text = "This is a test message with some sentiment."
        result = get_traditional_sentiment(text)

        # Individual scores should be between 0 and 1
        assert 0.0 <= result['neg'] <= 1.0
        assert 0.0 <= result['neu'] <= 1.0
        assert 0.0 <= result['pos'] <= 1.0

        # Compound score should be between -1 and 1
        assert -1.0 <= result['compound'] <= 1.0

        # Individual scores should sum to approximately 1
        score_sum = result['neg'] + result['neu'] + result['pos']
        assert abs(score_sum - 1.0) < 0.001  # Allow for small floating point errors

    @patch("ossai.sentiment.nltk.download")
    @patch("ossai.sentiment.SentimentIntensityAnalyzer")
    def test_get_analyzer_downloads_vader_on_lookup_error(self, mock_sia_class, mock_download, monkeypatch):
        """The LookupError path triggers an nltk download and retries initialization."""
        monkeypatch.setattr("ossai.sentiment._sia", None)
        successful_analyzer = MagicMock()
        mock_sia_class.side_effect = [LookupError("resource not found"), successful_analyzer]

        result = _get_analyzer()

        mock_download.assert_called_once_with("vader_lexicon", quiet=True)
        assert result is successful_analyzer

    @patch("ossai.sentiment._get_analyzer")
    def test_get_traditional_sentiment_exception_returns_neutral(self, mock_get_analyzer):
        """When polarity_scores raises, neutral scores are returned as fallback."""
        mock_analyzer = MagicMock()
        mock_analyzer.polarity_scores.side_effect = RuntimeError("unexpected failure")
        mock_get_analyzer.return_value = mock_analyzer

        result = get_traditional_sentiment("some valid text")

        assert result == {'neg': 0.0, 'neu': 1.0, 'pos': 0.0, 'compound': 0.0}