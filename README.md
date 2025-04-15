
# Kick TTS Chatbot

This project listens for Kick chat events, converts messages to speech using AWS Polly, and plays the audio locally. It connects directly to Kick’s chat event stream via websockets and allows you to toggle TTS functionality via command-line input. The TTS output is formatted as:

```
{sender} dice {message}
```

## Prerequisites

- **Windows 11**
- **Python 3.11**
  *Ensure Python is installed and added to your PATH.*
- An AWS account with valid credentials for Polly
- **Visual C++ Build Tools** (required for building certain packages)
- Proper folder permissions for temporary files (if needed)  
  *This guide does not cover detailed instructions for installing Python, Visual C++ Build Tools, or configuring folder permissions.*

## Setup Instructions

### 1. Clone the Repository

Place the following files in your project directory:
- `app.py`
- `requirements.txt`
- `.env.template`

### 2. Create a Virtual Environment

Open PowerShell in your project directory and run:

```powershell
py -3.11 -m venv venv
```

Then activate your virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Python Dependencies

With your virtual environment active, install the required packages:

```powershell
pip install -r requirements.txt
```

### 4. Configure AWS Credentials

Create a `.env` file in the project root by copying the provided template:

```powershell
copy .env.template .env
```

Open `.env` in your favorite text editor and set your AWS credentials, default region, and chatroom ID. Your `.env` template should look like:

```ini
# AWS stuff
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=

# Kick chatroom id
CHATROOM_ID=
```

### 5. Configure Temporary File Permissions

If you encounter temporary file permission issues during audio playback, create a folder (for example, `C:\MyTemp`) and ensure it has full control for your user. The code is configured to use this folder for temporary files.

### 6. Start the Application

Run the application by executing:

```powershell
python app.py
```

The application will:
- Print the initial TTS state.
- Connect to Kick’s chat event stream via websockets.
- Listen for incoming messages.
- When a message starts with an exclamation mark (`!`), it extracts the first word as the voice identifier and the remainder as the message.
- If the provided voice is `"m"`, the default voice `"Mia"` is used.
- It then converts the message to speech (formatted as `{sender} dice {message}`) using AWS Polly and plays the audio.

### 7. Usage

- **Chat Command Format:**  
  In Kick chat, send a message in the following unified format:
  ```
  !{voice_id} {message}
  ```
  For example, to use the default voice, you can send:
  ```
  !m Hola, ¿cómo estás?
  ```
  This produces a TTS output formatted as:
  ```
  luxinv dice Hola, ¿cómo estás?
  ```
  If you provide another voice identifier (for example, `!Pedro Buenas tardes`), the system will use that voice (after formatting it) for speech synthesis.

- **Toggle TTS:**  
  In the terminal where the app is running, type any command containing “on” or “off” to enable or disable TTS.

## Troubleshooting

- **Temporary File Permissions:**  
  If you see errors regarding permission denied for temporary files (e.g., in `C:\MyTemp\tmp*.wav`), ensure that the folder exists and that your user has full control over it.

- **Audio Playback Issues:**  
  The default playback uses ffmpeg via pydub. Ensure that ffmpeg is installed and available in your PATH.

- **AWS Credentials:**  
  Verify that your `.env` file has valid AWS credentials and that your region supports the voices you plan to use.

## License

This project is provided as-is with no warranty. Use at your own risk.

# TODO(luisvasquez): To implement a delay between consecutive chats (3 - 5 sec)