# Contributing to The Open-Source Slack AI App

First off, thanks for taking the time to contribute! 🥰

All types of contributions are encouraged and valued. See the [Table of Contents](#table-of-contents) for different ways to help and details about how this project handles them. Please make sure to read the relevant section before making your contribution. It will make it a lot easier for us maintainers and smooth out the experience for all involved. The community looks forward to your contributions. 🎉

> And if you like the project, but just don't have time to contribute, that's fine. There are other easy ways to support the project and show your appreciation, which we would also be very happy about:
> - Star the project
> - Tweet about it
> - Refer to this project elsewhere online
> - Mention the project at local meetups and tell your friends/colleagues

<!-- omit in toc -->
## Table of Contents

- [I Have a Question](#i-have-a-question)
- [I Want To Contribute](#i-want-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
- [Commit Messages](#commit-messages)

## I Have a Question

> If you want to ask a question, we assume that you have read the README.

Before you ask a question, it is best to search for existing [Issues](https://github.com/meetbryce/open-source-slack-ai/issues) that might help you. In case you have found a suitable issue and still need clarification, you can write your question in that issue.

If you then still feel the need to ask a question and need clarification, we recommend the following:

- Open an [Issue](https://github.com/meetbryce/open-source-slack-ai/issues/new).
- Provide as much context as you can about what you're running into.
- Provide project and platform versions (python, pip, etc), depending on what seems relevant.

## I Want To Contribute

> ### Legal Notice <!-- omit in toc -->
> When contributing to this project, you must agree that you have authored 100% of the content, that you have the necessary rights to the content and that the content you contribute may be provided under the project license.

### Reporting Bugs

<!-- omit in toc -->
#### Before Submitting a Bug Report

A good bug report shouldn't leave others needing to chase you up for more information. Therefore, we ask you to investigate carefully, collect information and describe the issue in detail in your report. Please complete the following steps in advance to help us fix any potential bug as fast as possible.

- Make sure that you are using the latest version.
- Determine if your bug is really a bug and not an error on your side e.g. using incompatible environment components/versions (Make sure that you have read the [documentation](). If you are looking for support, you might want to check [this section](#i-have-a-question)).
- To see if other users have experienced (and potentially already solved) the same issue you are having, check if there is not already a bug report existing for your bug or error in the [bug tracker](https://github.com/meetbryce/open-source-slack-aiissues?q=label%3Abug).
- Also make sure to search the internet (including Stack Overflow) to see if users outside of the GitHub community have discussed the issue.
- Collect information about the bug:
- Stack trace (Traceback)
- OS, Platform and Version (Windows, Linux, macOS, x86, ARM)
- Version of the interpreter, compiler, SDK, runtime environment, package manager, depending on what seems relevant.
- Possibly your input and the output
- Can you reliably reproduce the issue? And can you also reproduce it with older versions?

<!-- omit in toc -->
#### How Do I Submit a Good Bug Report?

> You must never report security related issues, vulnerabilities or bugs including sensitive information to the issue tracker, or elsewhere in public. Instead, sensitive bugs must be sent by email to support@bryceyork.com.
<!-- You may add a PGP key to allow the messages to be sent encrypted as well. -->

We use GitHub issues to track bugs and errors. If you run into an issue with the project:

- Open an [Issue](https://github.com/meetbryce/open-source-slack-ai/issues/new). Please use the provided issue template.
- Please provide as much context as possible and describe the *reproduction steps* that someone else can follow to recreate the issue on their own. This usually includes your code. For good bug reports you should isolate the problem and create a reduced test case.
- Provide the information you collected in the previous section.

Once it's filed:

- The project team will label the issue accordingly.
- A team member will try to reproduce the issue with your provided steps. If there are no reproduction steps or no obvious way to reproduce the issue, the team will ask you for those steps and mark the issue as `needs-repro`. Bugs with the `needs-repro` tag will not be addressed until they are reproduced.
- If the team is able to reproduce the issue, it will be marked `needs-fix`, as well as possibly other tags (such as `critical`), and the issue will be left to be implemented by someone.


### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for The Open-Source Slack AI App, **including completely new features and minor improvements to existing functionality**. Following these guidelines will help maintainers and the community to understand your suggestion and find related suggestions.

<!-- omit in toc -->
#### Before Submitting an Enhancement

- Make sure that you are using the latest version.
- Read the README carefully and find out if the functionality is already covered.
- Perform a [search](https://github.com/meetbryce/open-source-slack-ai/issues) to see if the enhancement has already been suggested. If it has, react to the initial post and add any relevant thoughts as a comment to the existing issue instead of opening a new one.
- It's up to you to make a strong case to convince the project's developers of the merits of this feature. Keep in mind that we want features that will be useful to the majority of our users and not just a small subset. If you're just targeting a minority of users, consider writing an add-on/plugin library.
- Consider submitting a PR. If the feature is well implemented and doesn't negatively impact the existing functionality, there's a good chance it will be merged.

<!-- omit in toc -->
#### How Do I Submit a Good Enhancement Suggestion?

Enhancement suggestions are tracked as [GitHub issues](https://github.com/meetbryce/open-source-slack-ai/issues).

> Please use the provided issue template

- Use a **clear and descriptive title** for the issue to identify the suggestion.
- Provide a **step-by-step description of the suggested enhancement** in as many details as possible.
- **Describe the current behavior** and **explain which behavior you expected to see instead** and why. At this point you can also tell which alternatives do not work for you.
- You may want to **include screenshots and animated GIFs** which help you demonstrate the steps or point out the part which the suggestion is related to. You can use [this tool](https://www.cockos.com/licecap/) to record GIFs on macOS and Windows, and [this tool](https://github.com/colinkeenan/silentcast) or [this tool](https://github.com/GNOME/byzanz) on Linux. <!-- this should only be included if the project has a GUI -->
- **Explain why this enhancement would be useful** to most The Open-Source Slack AI App users. You may also want to point out the other projects that solved it better and which could serve as inspiration.

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org) standard for our commit messages. This helps us write more readable messages that are easy to follow when looking through the project's commit history.

A basic conventional commit message should be structured as follows:

```
<type>: <description>

[optional body]

[optional footer(s)]
```

- **Type**: This is a category of changes. Some examples include `feat` (for a new feature), `fix` (for a bug fix), `docs` (for documentation changes), `style` (for formatting, missing semi colons, etc; no code change), `refactor` (for code change that neither fixes a bug nor adds a feature), `perf` (for code change that improves performance), `test` (for adding missing tests or correcting existing tests), `chore` (for changes to the build process or auxiliary tools and libraries such as documentation generation).

- **Description**: A brief description of the changes. The description is a short summary of the code changes, e.g., "add new user login button".

- **Body** (optional): A longer description of the commit, if necessary.

- **Footer** (optional): Any additional metadata about the commit, such as its breaking changes or closed issues.

Here's an example of a commit message following this format:

```
feat: add support for Claude

Adds support for Claude as the LLM. Includes associated documentation in the README and updates to example.env

See issue #123 for more details.
```

Please ensure that your commit messages follow this convention, as it is important for maintaining the project and generating meaningful change logs.