# The Open-Source Slack AI App

[![Test Coverage](https://api.codeclimate.com/v1/badges/49225ada2033154b15bf/test_coverage)](https://codeclimate.com/github/meetbryce/open-source-slack-ai/test_coverage) [![Maintainability](https://api.codeclimate.com/v1/badges/49225ada2033154b15bf/maintainability)](https://codeclimate.com/github/meetbryce/open-source-slack-ai/maintainability) ![GitHub License](https://img.shields.io/github/license/meetbryce/open-source-slack-ai) [![Static Badge](https://img.shields.io/badge/repo-analytics-violet?link=https%3A%2F%2Fmeetbryce.github.io%2Fopen-source-slack-ai--gh-stats%2Fmeetbryce%2Fopen-source-slack-ai%2Flatest-report%2Freport.html)](https://meetbryce.github.io/open-source-slack-ai--gh-stats/meetbryce/open-source-slack-ai/latest-report/report.html) [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/dwyl/esta/issues) ![X (formerly Twitter) Follow](https://img.shields.io/twitter/follow/meetbryce)

[//]: # "todo: youtube badge linking to walkthrough video?"

This repository is a ready-to-run basic Slack AI solution you can host yourself and unlock the ability to summarize
threads and channels on demand using OpenAI (support for alternative and open source LLMs will be added if there's
demand). The official Slack AI product looks great, but with limited access and add-on pricing, I decided to open-source
the version I built in September 2023. Learn more
about [how and why I built an open-source Slack AI](https://bryceyork.com/free-open-source-slack-ai/).

Once up and running (instructions for the whole process are provided below), all your Slack users will be able to
generate to both public and private:

1. **Thread summaries** - Generate a detailed summary of any Slack thread (powered by GPT-3.5-Turbo)
2. **Channel overviews** - Generate an outline of the channel's purpose based on the extended message history (powered
   by an ensemble of NLP models and a little GPT-4 to explain the analysis in natural language)
3. **Channel summaries since** - Generate a detailed summary of a channel's messages since a given point in time (powered by
   GPT-3.5-Turbo). Now with support for custom prompts! e.g. `/tldr_since anonymize the summary`. Note: this doesn't include threads yet.
4. **Full channel summaries** (experimental) - Generate a detailed summary of a channel's extended history (powered by
   GPT-3.5-Turbo). Now with support for custom prompts! e.g. `/tldr_extended anonymize the summary`. Note: this can get very long!

[//]: # "todo: demo video/gif of the 2 main features"

<!-- omit in toc -->

## Table of Contents

- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Customization](#customization)
- [Testing](#testing)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)

## Getting Started

Follow these instructions to get a copy of the project up and running on your local machine for development and testing
purposes.

### Prerequisites

Ensure you have the following preconfigured or installed on your local development machine:

- Python 3.9.x - 3.11.x
- OpenAI API key
- Slack App & associated API tokens
- [Poetry package manager](https://python-poetry.org/docs/#installation)
- [ngrok](https://ngrok.com/) (recommended)

### Installation

1. Clone the repository to your local machine.
2. Navigate to the project directory.
3. Install the required Python packages using Poetry:

```bash
poetry install
```

4. Install the dictionary model

```bash
poetry run python -m spacy download en_core_web_md
```

5. Create a `.env` file in the root directory of the project, and fill it with your API keys and tokens. Use
   the `example.env` file as a template.

```bash
cp example.env .env && open .env
```

<!-- omit in toc -->

#### Slack app configuration

Make a copy of `manifest.json` and change the request URL to your ngrok or server URL.

Create a new Slack app [here](https://api.slack.com/apps?new_app=1) and configure it using your `manifest.yaml`
file.

You shouldn't need to make any other changes but you can change the name, description, and other
copy related settings.

If you wish to adjust the name of the slash commands, you'll need to modify `slack_server.py`.

Once configured, retrieve the "Bot User OAuth Token" from the "Install App" page and add it to your `.env`
file as `SLACK_BOT_TOKEN`.

Then, on the Basic Information page under the App-Level Tokens heading create a token with the scop `connections:write`
and add it to your `.env` file as `SLACK_APP_TOKEN`.

### Usage

To run the application, run the FastAPI server:

```bash
poetry run uvicorn ossai.slack_server:app --reload
```

[//]: # "todo: improve the ngrok instructions"

You'll then need to expose the server to the internet using ngrok.

Run ngrok with the following command: `ngrok http 8000`

Then add the ngrok URL to your Slack app's settings.

[//]: # "todo: running ngrok and configuration of the Slack App"

### Customization

The main customization options are:

- Channel Summary: customize the ChatGPT prompt in `topic_analysis.py`
- Thread Summary: customize the ChatGPT prompt in `summarizer.py`

## Testing

This project uses `pytest` and `pytest-cov` to run tests and measure test coverage.

Follow these steps to run the tests with coverage:

1. Navigate to the project root directory.
2. Run the following command to execute the tests with coverage:

   ```bash
   pytest --cov=ossai tests/
   ```

   This command will run all the tests in the `tests/` directory and generate a coverage report for the `ossai`
   module.

3. After running the tests, you will see a report in your terminal that shows the percentage of code covered by tests
   and highlights any lines that are not covered.

Please note that if you're using a virtual environment, make sure it's activated before running these commands.

## Future Enhancements

- [x] Move to LangChain & LangSmith for extensibility, tracing, & control
- [x] leverage LangSmith's feedback capabilities to capture & learn from user feedback
- [x] Add a `/tldr_since` command to summarize a channel's messages since a given date
- [x] Add slack app setup details and sample app manifest to README
- [ ] Incorporate threaded conversations in channel-level summaries
- [ ] Implement evals suite to complement unit tests
- [ ] Add support for alternative and open-source LLMs
- [ ] Explore workflow for collecting data & fine-tuning models for cost reduction
- [ ] Add support for anonymized message summaries
- [ ] Leverage prompt tools like Chain of Destiny
- [ ] Add support for pulling supporting context from external sources like company knowledge bases
- [ ] Explore caching and other performance optimizations
- [ ] Explore sentiment analysis

## Contributing

I more than welcome contributions! Please read `CONTRIBUTING.md` for details on how to submit feedback, bugs, feature
requests,
enhancements, or your own pull requests.

## License

This project is licensed under the GPL-3.0 License - see the `LICENSE.md` file for details.
