import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from ossai.logging_config import logger
import threading

# Initialize the VADER sentiment analyzer
_sia = None
_lock = threading.Lock()

def _get_analyzer():
    """Lazy initialization of VADER sentiment analyzer with error handling"""
    global _sia
    if _sia is None:
        with _lock:
            if _sia is None:  # Double-check lock
                try:
                    # Try to initialize the analyzer
                    _sia = SentimentIntensityAnalyzer()
                except LookupError:
                    # If VADER lexicon is not found, download it
                    logger.info("VADER lexicon not found, downloading...")
                    try:
                        nltk.download("vader_lexicon", quiet=True)
                        _sia = SentimentIntensityAnalyzer()
                        logger.info("VADER lexicon downloaded successfully")
                    except Exception as e:
                        logger.error(f"Failed to download VADER lexicon: {e}")
                        raise
    return _sia

def get_traditional_sentiment(text: str) -> dict:
    """
    Calculate sentiment polarity scores using NLTK's VADER sentiment analyzer.
    
    Args:
        text (str): The text to analyze for sentiment
        
    Returns:
        dict: A dictionary containing sentiment scores with keys:
            - 'neg': Negative sentiment score (0.0 to 1.0)
            - 'neu': Neutral sentiment score (0.0 to 1.0)  
            - 'pos': Positive sentiment score (0.0 to 1.0)
            - 'compound': Compound score (-1.0 to 1.0)
    """
    if not text or not text.strip():
        # Return neutral scores for empty or whitespace-only text
        return {'neg': 0.0, 'neu': 1.0, 'pos': 0.0, 'compound': 0.0}
    
    try:
        analyzer = _get_analyzer()
        scores = analyzer.polarity_scores(text)
        return scores
    except Exception as e:
        logger.error(f"Error calculating sentiment for text: {e}")
        # Return neutral scores as fallback
        return {'neg': 0.0, 'neu': 1.0, 'pos': 0.0, 'compound': 0.0} 