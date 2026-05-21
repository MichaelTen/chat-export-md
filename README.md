# Chat Export MD | chat-export-md

Convert exported ChatGPT conversations into clean, organized Markdown files for archiving, search, and knowledge-base workflows.

## Overview

Chat Export MD is a small Python utility that reads exported ChatGPT conversation JSON files and writes each conversation thread as its own Markdown file. It is useful for keeping a local archive, importing conversations into notes apps, or building a searchable knowledge base from past chats.

The project starts from [`MichaelTen/chatgpt-markdown`](https://github.com/MichaelTen/chatgpt-markdown), which is a fork of the original [`gavi/chatgpt-markdown`](https://github.com/gavi/chatgpt-markdown).

## Export Your ChatGPT Data

You can export your ChatGPT data from OpenAI using the official instructions:

<https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data>

After downloading and extracting the export, place the conversation JSON files in an input directory and pass that directory to the converter.

## Requirements

- Python 3.x
- A terminal or command prompt
- No third-party Python packages

## Usage

Run the converter with an input directory and an output directory:

```bash
python .\convert-json-v18.py .\chats-json .\chats-parsed-md-v1
```

Recommended usage:

```bash
python .\convert-json-v18.py .\chats-json .\chats-parsed-md-v1 --use-date-folders --auto-version-output
```

Arguments:

- `input_dir`: Directory containing exported ChatGPT conversation JSON files.
- `output_dir`: Directory where Markdown files should be written.
- `--use-date-folders`: Optional flag that stores files in folders named by conversation date, such as `2023-01-01`.
- `--auto-version-output`: Optional flag that automatically versions the output directory so previous converted exports are not overwritten.

## Output

The script creates one Markdown file per conversation thread. When date folders are enabled, each Markdown file is placed inside a folder matching the conversation date. When automatic output versioning is enabled, the converter creates a versioned output path instead of overwriting an existing output directory.

## Project Structure

```text
.
├── convert-json-v18.py
├── LICENSE
└── README.md
```

## License

This project is licensed under the GNU Affero General Public License v3.0 or later. See [`LICENSE`](LICENSE) for details.

This project is derived from MIT-licensed upstream work:

- [`MichaelTen/chatgpt-markdown`](https://github.com/MichaelTen/chatgpt-markdown)
- [`gavi/chatgpt-markdown`](https://github.com/gavi/chatgpt-markdown)

The original MIT license notice and attribution should be preserved for upstream-derived portions of the code.
