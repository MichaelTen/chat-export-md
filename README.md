# Chat Export MD | chat-export-md

Convert exported ChatGPT conversation JSON files into clean, organized Markdown files for local archiving, search, and knowledge-base workflows.

## Overview

This project uses `convert-json-v18.py` to read ChatGPT export JSON and write one Markdown file per conversation. It supports both older single-file exports and newer exports split across many `conversations-###.json` files.

The raw export files should stay in `chats-json`. The converter reads those files but does not modify them.

The project starts from [`MichaelTen/chatgpt-markdown`](https://github.com/MichaelTen/chatgpt-markdown), which is a fork of the original [`gavi/chatgpt-markdown`](https://github.com/gavi/chatgpt-markdown).

## Export Your ChatGPT Data

You can export your ChatGPT data from OpenAI using the official instructions:

<https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data>

After downloading and extracting the export, place the conversation JSON files in `chats-json` or pass another JSON file/folder path to the converter.

## Requirements

- Python 3.x
- A terminal or command prompt
- No third-party Python packages

## Recommended Usage

From this folder:

```powershell
python .\convert-json-v18.py .\chats-json .\chats-parsed-md-v1 --use-date-folders --auto-version-output
```

For more frequent progress updates:

```powershell
python .\convert-json-v18.py .\chats-json .\chats-parsed-md-v1 --use-date-folders --auto-version-output --progress-interval 100
```

## Arguments

- `input_path`: JSON file or directory containing exported ChatGPT conversation JSON files.
- `output_dir`: Base directory where Markdown files should be written.
- `--use-date-folders`: Store files in folders named by conversation date, such as `2024-05-21`.
- `--auto-version-output`: Use the first empty/new versioned output folder derived from `output_dir`.
- `--progress-interval N`: Print progress after every `N` written Markdown files. Use `0` to only print start and finish.
- `--include-system`: Include system messages.
- `--include-hidden`: Include visually hidden exported messages.
- `--include-reasoning`: Include exported reasoning/thought summary records.

## Output Versioning

With `--auto-version-output`, the converter will not overwrite a populated parsed folder.

For example, when this command is run:

```powershell
python .\convert-json-v18.py .\chats-json .\chats-parsed-md-v1 --use-date-folders --auto-version-output
```

The script checks folders in order:

- `chats-parsed-md-v1`
- `chats-parsed-md-v2`
- `chats-parsed-md-v3`

It writes to the first folder that does not exist or is empty.

## Markdown Cleanup

The converter cleans current ChatGPT export formats into more readable Markdown, including:

- Voice-to-text messages stored as normal text transcript content.
- Image and multimodal messages as placeholders like `[image: file-id]` or `[image: name.ext]` when the export includes an extension.
- ChatGPT private markers such as `entity`, `products`, `product_entity`, `image_group`, citations, and link-title markers.
- Tool-call JSON blocks such as search, open, click, weather, finance, and similar calls into short readable summaries.

## Project Structure

```text
.
|-- README.md
|-- LICENSE
|-- NOTICE.md
|-- command.txt
|-- convert-json-v18.py
|-- chats-json/
|-- chats-parsed-md-v1/
|-- chats-parsed-md-v2/
`-- tmp/
```

## Notes

- `chats-json/` is the raw ChatGPT export input folder.
- `chats-parsed-md-v*/` folders are generated Markdown output folders.
- `tmp/` is for test output and scratch runs.
- Large exports can take several minutes, especially when writing thousands of small files to a network drive.

## License And Attribution

This project is licensed under the GNU Affero General Public License v3.0 or later. See [`LICENSE`](LICENSE) for details.

Additional attribution and upstream notices are in [`NOTICE.md`](NOTICE.md).

This project is derived from MIT-licensed upstream work:

- [`MichaelTen/chatgpt-markdown`](https://github.com/MichaelTen/chatgpt-markdown)
- [`gavi/chatgpt-markdown`](https://github.com/gavi/chatgpt-markdown)

Preserve the original MIT license notice and attribution for upstream-derived portions of the code.

