from datetime import datetime
import functools
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


def to_pdf(func):
    """
    Decorator to convert the result of slack_context's get_parsed_messages to a PDF file for use in NotebookLM.
    Usage:
    @to_pdf
    def get_parsed_messages(slack_context: SlackContext, *args, **kwargs):
        ...
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # Create a filename based on the function name
        filename = f"{func.__name__}.pdf"
        file_path = os.path.join(os.getcwd(), filename)

        doc = SimpleDocTemplate(file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"Slack Conversation Log", styles["Heading1"]))
        elements.append(
            Paragraph(
                f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            )
        )
        elements.append(Paragraph("<br/><br/><hr/><br/>", styles["Normal"]))

        for message in result:
            elements.append(Paragraph(message, styles["Normal"]))
            elements.append(Paragraph("<br/><br/>", styles["Normal"]))

        doc.build(elements)

        # Return the original result
        return result

    return wrapper
