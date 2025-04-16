# tts_service_enhanced.py

import boto3
import botocore.exceptions # For specific AWS errors
import io
import logging
import os
import tempfile # For optional file output
from typing import Optional, Union, Dict, Any

# Third-party imports - ensure installed: pip install pydub boto3
try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
    from pydub.playback import play
except ImportError:
    print("Error: pydub package not found. Please install it: pip install pydub")
    exit(1)

# --- Configure Logging ---
# It's better to get the logger passed in or configure it outside the class
# but keeping it simple based on the original structure.
# Example: logger = logging.getLogger(__name__)

class TTSService:
    """
    A service class for synthesizing speech using AWS Polly and playing it back.

    Requires:
        - boto3: AWS SDK for Python. Credentials must be configured (e.g., via
          environment variables AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
          AWS_SESSION_TOKEN, AWS_REGION, or IAM role).
        - pydub: For audio manipulation.
        - ffmpeg (or libav): Required by pydub for handling MP3 and other non-PCM/WAV formats.
          Ensure ffmpeg is installed and accessible in your system's PATH.
        - Playback library: pydub relies on simpleaudio, pyaudio, or ffplay/avplay
          for the play() function. Ensure one is installed (e.g., pip install simpleaudio).
    """

    # Supported Polly formats by pydub (with ffmpeg for mp3/ogg)
    # PCM requires knowing sample rate/width/channels from Polly response if used directly
    SUPPORTED_FORMATS = ['mp3', 'ogg_vorbis', 'pcm']

    def __init__(
        self,
        aws_region: str,
        logger: logging.Logger,
        default_voice: str = 'Mia', # Example: Consider Joanna, Matthew, Amy for neural
        default_engine: str = 'neural', # Default to neural, fallback implemented
        boto3_session: Optional[boto3.Session] = None
    ):
        """
        Initializes the TTSService.

        Args:
            aws_region: The AWS region where Polly service is located (e.g., 'us-east-1').
            logger: A configured Python logger instance.
            default_voice: The default AWS Polly voice ID to use.
            default_engine: The default AWS Polly engine ('standard' or 'neural').
            boto3_session: An optional pre-configured boto3 Session object.
                           If None, a new session is created.
        """
        self.logger = logger
        self.default_voice = default_voice
        self.default_engine = default_engine
        self.aws_region = aws_region

        try:
            session = boto3_session or boto3.Session(region_name=self.aws_region)
            # Explicitly check if credentials are found early
            if session.get_credentials() is None:
                raise botocore.exceptions.NoCredentialsError()

            self.client = session.client('polly')
            # Test connection/credentials with a low-impact call
            self.client.describe_voices()
            self.logger.info(f"AWS Polly client initialized successfully for region {self.aws_region}")
        except botocore.exceptions.NoCredentialsError:
            self.logger.exception("AWS credentials not found. Please configure credentials.")
            raise ConnectionError("AWS credentials not found.")
        except botocore.exceptions.ClientError as e:
             self.logger.exception(f"AWS ClientError during initialization: {e}")
             # Specifically check for common issues
             if "invalid region" in str(e).lower():
                  raise ValueError(f"Invalid AWS region specified: {self.aws_region}") from e
             elif e.response['Error']['Code'] == 'AccessDeniedException':
                  raise PermissionError("AWS Polly access denied. Check IAM permissions.") from e
             else:
                 raise ConnectionError(f"Failed to initialize Polly client: {e}") from e
        except Exception as e: # Catch any other unexpected initialization errors
            self.logger.exception(f"Unexpected error during Polly client initialization: {e}")
            raise ConnectionError(f"Unexpected error initializing Polly client: {e}") from e


    def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        engine: Optional[str] = None,
        output_format: str = 'mp3',
        sample_rate: Optional[str] = None, # e.g., "22050", required for PCM
        output_file: Optional[str] = None
    ) -> Union[bytes, str]:
        """
        Synthesizes speech using AWS Polly.

        Args:
            text: The text to synthesize. Max 3000 billed characters, 6000 total.
                  SSML text must be enclosed in <speak> tags.
            voice_id: The Polly voice ID to use. Uses instance default if None.
            engine: The Polly engine ('standard' or 'neural'). Uses instance default if None.
                    Neural voices require the neural engine.
            output_format: The desired audio format ('mp3', 'ogg_vorbis', 'pcm').
            sample_rate: The sample rate in Hz (e.g., "8000", "16000", "22050", "24000").
                         Required for PCM, optional for others (Polly uses defaults).
                         Check Polly docs for supported rates per voice/engine.
            output_file: Optional. If provided, saves the audio to this file path
                         and returns the path. If None (default), returns the raw audio bytes.

        Returns:
            Union[bytes, str]: The raw audio bytes if output_file is None,
                               otherwise the path to the saved output file.

        Raises:
            ValueError: If parameters are invalid (e.g., unsupported format, invalid voice).
            ConnectionError: If unable to connect to AWS Polly or authentication fails.
            RuntimeError: For other Polly API errors.
        """
        if not text:
            raise ValueError("Input text cannot be empty.")

        voice = voice_id or self.default_voice
        selected_engine = engine or self.default_engine

        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}. Choose from: {self.SUPPORTED_FORMATS}")

        polly_params: Dict[str, Any] = {
            'Text': text,
            'VoiceId': voice,
            'OutputFormat': output_format,
            'Engine': selected_engine
        }
        if sample_rate:
            polly_params['SampleRate'] = str(sample_rate) # Polly expects string

        self.logger.debug(f"Requesting Polly synthesis: Voice={voice}, Engine={selected_engine}, Format={output_format}"
                         f"{', SampleRate='+sample_rate if sample_rate else ''}")

        try:
            response = self.client.synthesize_speech(**polly_params)
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            self.logger.error(f"AWS Polly API error ({error_code}): {error_msg}")
            # Handle specific common errors
            if error_code == 'ValidationException':
                 # Can be caused by various issues: invalid voice/engine combo, bad SSML, text length limits, invalid sample rate
                 if "voice" in error_msg.lower():
                     raise ValueError(f"Invalid VoiceId '{voice}' specified.") from e
                 elif "engine" in error_msg.lower() and "neural" in error_msg.lower():
                     raise ValueError(f"Voice '{voice}' may not support the '{selected_engine}' engine.") from e
                 elif "sample rate" in error_msg.lower():
                      raise ValueError(f"Invalid SampleRate '{sample_rate}' for the specified configuration.") from e
                 elif "SSML" in error_msg:
                     raise ValueError(f"Invalid SSML markup provided: {error_msg}") from e
                 else:
                     raise ValueError(f"Polly validation failed: {error_msg}") from e
            elif error_code == 'AccessDeniedException':
                raise ConnectionError("AWS Polly access denied. Check IAM permissions.") from e
            elif error_code == 'ThrottlingException':
                 raise RuntimeError("AWS Polly request throttled. Please try again later.") from e
            else:
                 raise RuntimeError(f"AWS Polly synthesis failed: {error_msg}") from e
        except Exception as e: # Catch other potential issues like network errors
             self.logger.exception(f"Unexpected error during Polly API call: {e}")
             raise ConnectionError(f"Failed to call Polly API: {e}") from e

        # Process the audio stream
        try:
            audio_stream = response.get('AudioStream')
            if not audio_stream:
                self.logger.error("Polly response missing 'AudioStream'. Response: %s", response)
                raise RuntimeError("Polly synthesis returned an invalid response (no AudioStream).")

            audio_bytes = audio_stream.read()

            if output_file:
                self.logger.info(f"Saving synthesized audio to: {output_file}")
                # Ensure directory exists if path includes directories
                output_dir = os.path.dirname(output_file)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                with open(output_file, 'wb') as f:
                    f.write(audio_bytes)
                return output_file
            else:
                # Return raw bytes if no output file specified
                self.logger.debug(f"Returning {len(audio_bytes)} bytes of synthesized audio data.")
                return audio_bytes

        except IOError as e:
            self.logger.exception(f"Failed to write audio to file {output_file}: {e}")
            raise RuntimeError(f"Failed to write audio file: {e}") from e
        except Exception as e:
             self.logger.exception(f"Error processing Polly audio stream: {e}")
             raise RuntimeError(f"Failed to process audio stream: {e}") from e


    def play_tts(self, text: str, voice_id: Optional[str] = None) -> bool:
        """
        Synthesizes speech using AWS Polly (with standard/neural fallback)
        and plays it directly from memory using pydub.

        Args:
            text: The text content to speak.
            voice_id: Optional specific voice ID to use. Falls back to instance default.

        Returns:
            bool: True if playback was successful, False otherwise.
        """
        voice = voice_id or self.default_voice
        audio_bytes: Optional[bytes] = None
        used_engine = None

        # --- Try Neural Engine First (usually higher quality) ---
        if self.default_engine == 'neural' or 'neural' not in self.default_engine: # Try neural if it's default or if standard isn't explicitly default
            self.logger.debug(f"Attempting synthesis with NEURAL engine (voice: {voice})...")
            try:
                audio_bytes = self.synthesize_speech(
                    text, voice_id=voice, engine='neural', output_format='mp3', output_file=None
                )
                used_engine = 'neural'
            except ValueError as e: # Catch config errors like voice not supporting neural
                self.logger.warning(f"Neural engine configuration error: {e}. Falling back to standard.")
            except RuntimeError as e: # Catch API/throttling errors
                 self.logger.error(f"Neural engine synthesis failed: {e}. Falling back to standard.")
            except ConnectionError as e:
                 self.logger.error(f"AWS Connection Error (Neural): {e}. Cannot proceed.")
                 return False
            except Exception as e_neural: # Catch unexpected errors
                self.logger.exception(f"Unexpected error with neural engine: {e_neural}. Falling back.")

        # --- Fallback to Standard Engine ---
        if audio_bytes is None:
            self.logger.debug(f"Attempting synthesis with STANDARD engine (voice: {voice})...")
            try:
                audio_bytes = self.synthesize_speech(
                    text, voice_id=voice, engine='standard', output_format='mp3', output_file=None
                )
                used_engine = 'standard'
            except (ValueError, RuntimeError, ConnectionError) as e_std:
                 self.logger.error(f"Standard engine synthesis also failed: {e_std}")
                 return False # Both engines failed
            except Exception as e_std_unexpected: # Catch unexpected errors
                self.logger.exception(f"Unexpected error with standard engine: {e_std_unexpected}")
                return False

        # --- Playback ---
        if audio_bytes:
            self.logger.info(f"Synthesized successfully using {used_engine} engine. Playing audio...")
            try:
                # Load audio data from bytes using io.BytesIO
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                self.logger.debug(f"Audio loaded into pydub (Duration: {len(audio_segment) / 1000.0:.2f}s)")

                # Play the audio
                play(audio_segment)
                self.logger.info("Audio playback finished.")
                return True
            except CouldntDecodeError as e_decode:
                 self.logger.error(f"Pydub decoding error: {e_decode}")
                 self.logger.error("Ensure 'ffmpeg' is installed and accessible in your system PATH.")
                 return False
            except Exception as e_play: # Catch errors from play() (e.g., no playback device)
                self.logger.exception(f"Audio playback failed: {e_play}")
                self.logger.error("Ensure a playback device is available and a pydub playback backend (e.g., simpleaudio, ffplay) is installed/working.")
                return False
        else:
            # Should not happen if fallback logic is correct, but as a safeguard:
            self.logger.error("Synthesis seemed to succeed but no audio data was available for playback.")
            return False


# --- Example Usage ---
if __name__ == '__main__':
    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("tts_example")

    # --- Configuration ---
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1') # Get region from env or default
    # Ensure AWS Credentials are configured in your environment (e.g., ~/.aws/credentials, env vars, IAM role)

    try:
        # Initialize the service
        tts_service = TTSService(aws_region=AWS_REGION, logger=main_logger, default_voice='Joanna') # Joanna supports neural

        # --- Example 1: Play directly ---
        main_logger.info("\n--- Example 1: Playing synthesized speech directly ---")
        text_to_speak = "Hello from AWS Polly! This audio is played directly from memory."
        success = ts_service.play_tts(text_to_speak)
        if success:
             main_logger.info("Example 1 finished successfully.")
        else:
             main_logger.error("Example 1 failed.")


        # --- Example 2: Synthesize to a file ---
        main_logger.info("\n--- Example 2: Synthesizing speech to a file ---")
        file_text = "This speech will be saved to a file named 'polly_output.mp3'."
        try:
            # Create a temporary directory for output
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, "polly_output.mp3")
            # Use a neural voice explicitly
            file_path = tts_service.synthesize_speech(
                file_text,
                voice_id='Matthew', # Matthew supports neural
                engine='neural',
                output_format='mp3',
                output_file=output_path
            )
            main_logger.info(f"Audio saved successfully to: {file_path}")
            # You could optionally play this file now using pydub or another tool
            # try:
            #     audio = AudioSegment.from_mp3(file_path)
            #     play(audio)
            # except Exception as e:
            #     main_logger.error(f"Failed to play saved file {file_path}: {e}")

        except (ValueError, RuntimeError, ConnectionError, IOError) as e:
            main_logger.error(f"Example 2 failed: {e}")
        finally:
            # Clean up the temporary directory
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    # Remove files and directory - consider shutil.rmtree for non-empty dirs
                    if 'output_path' in locals() and os.path.exists(output_path):
                         os.remove(output_path)
                    os.rmdir(temp_dir)
                    main_logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                except OSError as e_clean:
                    main_logger.error(f"Error cleaning up temp directory {temp_dir}: {e_clean}")


        # --- Example 3: Synthesize PCM data (requires sample rate) ---
        main_logger.info("\n--- Example 3: Synthesizing raw PCM data (bytes) ---")
        pcm_text = "This is raw PCM audio data."
        try:
             pcm_bytes = tts_service.synthesize_speech(
                  pcm_text,
                  voice_id='Joanna',
                  engine='neural',
                  output_format='pcm',
                  sample_rate="16000", # Specify sample rate for PCM! Check Polly docs for valid rates.
                  output_file=None # Get bytes
             )
             if isinstance(pcm_bytes, bytes):
                  main_logger.info(f"Successfully received {len(pcm_bytes)} bytes of PCM data.")
                  # You would typically process these bytes directly with an audio library
                  # that understands raw PCM (e.g., sounddevice, pyaudio)
                  # Example: Playing PCM with sounddevice (if installed: pip install sounddevice numpy)
                  # try:
                  #     import numpy as np
                  #     import sounddevice as sd
                  #     # Assuming 16-bit mono PCM
                  #     pcm_data = np.frombuffer(pcm_bytes, dtype=np.int16)
                  #     sd.play(pcm_data, samplerate=16000)
                  #     sd.wait()
                  # except ImportError:
                  #     main_logger.warning("sounddevice/numpy not installed, cannot play PCM example.")
                  # except Exception as e_pcm_play:
                  #     main_logger.error(f"Failed to play PCM data: {e_pcm_play}")
             else:
                  main_logger.error("Expected bytes for PCM data, but received something else.")

        except (ValueError, RuntimeError, ConnectionError) as e:
            main_logger.error(f"Example 3 failed: {e}")


    except (ConnectionError, PermissionError, ValueError) as e:
        main_logger.error(f"Failed to initialize TTSService: {e}")
    except Exception as e:
        main_logger.exception(f"An unexpected error occurred in the main example: {e}")
