Developer docs
==================================

## 📝 Prerequisites
* ffmpeg (minimum version 5, version 6 recommended), must be available in the path so install at OS level
* Python 3.11 is minimal required (or check the pyproject for current required version)
* [Python venv](https://docs.python.org/3/library/venv.html)

We recommend developing on a (recent) MacOS or Linux machine.
It is recommended to use Visual Studio Code as your IDE, since launch files to start Music Assistant are provided as part of the repository. Furthermore, the current code base is not verified to work on a native Windows machine. If you would like to develop on a Windows machine, install [WSL2](https://code.visualstudio.com/blogs/2019/09/03/wsl2) to increase your swag-level 🤘.

## 🚀 Setting up your development environment

### Using Devcontainer/Codespace
* Using Codespace: Create/open your Codespace, and wait for the creation
* Using VSCode Dev Container locally: `Dev Containers: Open Folder in Container...`, select the root of the project, and wait for the creation
* Once VSCode has loaded, after a few seconds a terminal should pop with `Running postCreateCommand...`. Wait for the dependencies to install. You can monitor it with `Codespaces: View Creation Log`
* Select the right Python interpreter with `Python: Select Interpreter`, and choose `./.venv/bin/python`
* Hit (Fn +) F5 to start Music Assistant locally
* Go to the `PORTS` tab in the bottom panel, open the `Forwarded Address` for the port `8095` to access the pre-compiled UI of Music Assistant 🎉

### Manually
With this repository cloned locally, execute the following commands in a terminal from the root of your repository:
* Run our development setup script to setup the development environment:
* `scripts/setup.sh` (creates a new separate virtual environment to nicely separate the project dependencies)
* The setup script will create a separate virtual environment (if needed), install all the project/test dependencies and configure pre-commit for linting and testing.
* Debug: Hit (Fn +) F5 to start Music Assistant locally
* The pre-compiled UI of Music Assistant will be available at `localhost:8095` 🎉


The Music Assistant server is fully built in Python. The Python language has no real supported for multi-threading. This is why Music Assistant heavily relies on asyncio to handle blocking IO. It is important to get a good understanding of asynchronous programming before building your first provider. [This](https://www.youtube.com/watch?v=M-UcUs7IMIM) video is an excellent first step in the world of asyncio.

## Building a new Music Provider
A Music Provider is the provider type that adds support for a 'source of music' to Music Assistant. Spotify and Youtube Music are examples of a Music Provider, but also Filesystem and SMB can be put in the Music Provider category. All Providers (of all types) can be found in the `music_assistant/server/providers` folder.

TIP: We have created a template/stub provider in `music_assistant/server/providers/_template_music_provider` to get you started fast!


**Adding the necessary files for a new Music Provider**

Add a new folder to the `providers` folder with the name of provider. Add two files inside:
1. `__init__.py`. This file contains the Python code of your provider.
2. `manifest.json`. This file contains metadata and configuration for your provider.

**Configuring the manifest.json file**

The easiest way to get start is to copy the contents of the manifest of an existing Music Provider, e.g. Spotify or Youtube Music. See [the manifest section](#⚙️-manifest-file) for all available properties.

**Creating the provider**

Create a file called `__init__.py` inside the folder of your provider. This file will contain the logic for the provider. All Music Providers must inherit from the [`MusicProvider`](./music_assistant/server/models/music_provider.py) base class and override the necessary functions where applicable. A few things to note:
* The `setup()` function is called by Music Assistant upon initialization of the provider. It gives you the opportunity the prepare the provider for usage. For example, logging in a user or obtaining a token can be done in this function.
* A provider should let Music Assistant know which [`ProviderFeatures`](./music_assistant/common/models/enums.py) it supports by implementing the property `supported_features`, which returns a list of `ProviderFeatures`.
* The actual playback of audio in Music Assistant happens in two phases:
    1. `get_stream_details()` is called to obtain information about the audio, like the quality, format, # of channels etc.
    2. `get_audio_stream()` is called to stream raw bytes of audio to the player. There are a few [helpers](./music_assistant/server/helpers/audio.py) to help you with this. Note that this function is not applicable to direct url streams.
* Examples:
    1. Streaming raw bytes using an external executable (librespot) to get audio, see the [Spotify](./music_assistant/server/providers/spotify/__init__.py) provider as an example
    2. Streaming a direct URL, see the [Youtube Music](.//music_assistant/server/providers/ytmusic/__init__.py) provider as an example
    3. Streaming an https stream that uses an expiring URL, see the [Qobuz](./music_assistant/server/providers/qobuz/__init__.py) provider as an example


## ▶️ Building your own Player Provider
A Player Provider is the provider type that adds support for a 'target of playback' to Music Assistant. Sonos, Chromecast and Airplay are examples of a Player Provider.
All Providers (of all types) can be found in the `music_assistant/server/providers` folder.

TIP: We have created a template/stub provider in `music_assistant/server/providers/_template_player_provider` to get you started fast!

## 💽 Building your own Metadata Provider
Will follow soon™

## 🔌 Building your own Plugin Provider
Will follow soon™

## ⚙️ Manifest file
The manifest file contains metadata and configuration about a provider. The supported properties are:
| Name  | Description  | Type  |
|---|---|---|
| type  | `music`, `player`, `metadata` or `plugin`  | string  |
| domain  | The internal unique id of the provider, e.g. `spotify` or `ytmusic`  | string  |
| name  | The full name of the provider, e.g. `Spotify` or `Youtube Music`  | string  |
| description  | The full description of the provider  | string  |
| codeowners  | List of Github names of the codeowners of the provider  | array[string]  |
| config_entries  | List of configurable properties for the provider, e.g. `username` or `password`*. | array[object]  |
| config_entries.key  | The unique key of the config entry, used to obtain the value in the provider code  | string  |
| config_entries.type  | The type of the config entry. Possible values: `string`, `secure_string` (for passwords), `boolean`, `float`, `integer`, `label` (for a single line of text in the settings page)  | string  |
| config_entries.label | The label of the config entry. Used in the settings page | string |
| requirements | List of requirements for the provider in pip string format. Supported values are `package==version` and `git+https://gitrepoforpackage` | array[string]
| documentation | URL to the Github discussion containing the documentation for the provider. | string |
| multi_instances | Whether multiple instances of the configuration are supported, e.g. multiple user accounts for Spotify | boolean |

\* These `config_entries` are used to automatically generate the settings page for the provider in the front-end. The values can be obtained via `self.config.get_value(key)`.
