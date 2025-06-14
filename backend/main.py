import os
import time
import json
import re

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Twilio Credentials (from .env)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# OpenAI Client (from .env)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_MODEL = "gpt-4o-mini" # A cost-effective and capable model

# --- Flask App Initialization ---
app = Flask(__name__)

# --- In-Memory Storage ---
# These dictionaries will store data only while the app is running.
# Data will be lost if the app restarts.
candidate_profiles = {} # Key: phone_number, Value: {field: value, ...}
conversation_states = {} # Key: phone_number, Value: {currentStep: "STEP_NAME"}

# --- Interview Flow Definition (THIS VERSION DOES NOT HAVE "NOTICE PERIOD") ---
interview_flow_config = [
    {"step": "START", "question": "Hello! Thank you for connecting. This is an automated HR screening call. First, could you please tell me about your experience with Java, perhaps in terms of years or projects?", "field": "javaExperience"},
    {"step": "ASK_SALARY", "question": "Thank you. Next, what is your expected annual salary?", "field": "expectedSalary"},
    {"step": "ASK_TIMESLOT", "question": "Understood. Finally, we have interview slots available on Monday at 2 PM, Tuesday at 10 AM, and Wednesday at 4 PM. Which of these times would work best for you?", "field": "availableTimeSlots"},
    {"step": "END", "question": "Thank you for providing that information. We have recorded your details and will be in touch shortly. Goodbye!", "field": None}
]

def get_flow_info(step_name: str):
    """Retrieves information for a specific step in the interview flow."""
    for step_info in interview_flow_config:
        if step_info["step"] == step_name:
            return step_info
    return None

def get_next_step_name(current_step_name: str):
    """Determines the name of the next step in the interview flow."""
    for i, step_info in enumerate(interview_flow_config):
        if step_info["step"] == current_step_name:
            if i + 1 < len(interview_flow_config):
                return interview_flow_config[i + 1]["step"]
    return "END"

def parse_and_update_profile(field: str, user_response: str, candidate_profile: dict):
    """
    Uses LLM to parse user response for a specific field and update candidate profile.
    Returns the updated candidate_profile dictionary.
    """
    print(f"Parsing response for field '{field}': '{user_response}'")
    extracted_value = "N/A" # Default if nothing specific is extracted

    if field == "javaExperience":
        prompt = f"The user just spoke about their Java experience. Summarize their Java experience in 1-2 sentences from this text: '{user_response}'"
        llm_response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        extracted_value = llm_response if llm_response else "N/A"

    elif field == "expectedSalary":
        prompt = f"The user stated their expected salary. Extract the numerical value (e.g., '50000', '50K', '5 lakhs', '500000') and the currency/unit if mentioned. User response: '{user_response}'. Respond with only the extracted salary information (e.g., '50,000 USD' or '15 Lakhs'). If no salary is found, respond 'Not specified'."
        llm_response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        extracted_value = llm_response if llm_response and llm_response.lower() != "not specified" else "Not specified"

    elif field == "availableTimeSlots":
        prompt = f"""
        The user was offered interview slots on 'Monday at 2 PM, Tuesday at 10 AM, and Wednesday at 4 PM'.
        Based on their response, identify which of these slots they preferred.
        User response: '{user_response}'
        Respond with only the chosen slot (e.g., 'Tuesday at 10 AM'). If multiple or none are chosen, pick the clearest single option or respond 'No specific slot chosen'.
        """
        llm_response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        extracted_value = llm_response if llm_response and llm_response.lower() != "no specific slot chosen" else "No specific slot chosen"
    
    candidate_profile[field] = extracted_value
    print(f"Updated candidate profile for field '{field}': {extracted_value}")
    return candidate_profile

# --- Flask API Endpoint for Twilio Voice Webhook ---
@app.route("/voice", methods=['POST'])
def voice_interview():
    """Handles incoming voice calls from Twilio."""
    from_number = request.form['From']
    speech_result = request.form.get('SpeechResult', '').strip()
    recognition_status = request.form.get('SpeechResultStatus', '')
    
    print(f"\n--- Incoming Call from: {from_number} ---")
    print(f"SpeechResult (if any): '{speech_result}'")
    print(f"Speech Recognition Status: '{recognition_status}'")

    resp = VoiceResponse()

    current_step_name = "START" # Default for new calls or initial webhook
    # Initialize with phone number; other fields will be added as collected
    candidate_profile_data = {"phoneNumber": from_number} 
    
    # --- Retrieve Conversation State from Memory ---
    if from_number in conversation_states:
        current_step_name = conversation_states[from_number]["currentStep"]
        print(f"Existing state for {from_number}. Loaded step: {current_step_name}")
    else:
        print(f"New call from {from_number}. Initial step: {current_step_name}")
        # Initialize an empty profile for new numbers if not already existing
        candidate_profiles[from_number] = {"phoneNumber": from_number}


    # --- Retrieve Candidate Profile from Memory ---
    # Ensure candidate_profile_data reflects the latest state for the phone_number
    # It might have been initialized as empty above for new calls, but here we load existing data if any.
    if from_number in candidate_profiles:
        candidate_profile_data = candidate_profiles[from_number]
        print(f"Existing candidate profile found for {from_number}: {candidate_profile_data}")
    # else: (Already handled by initializing an empty profile for new numbers)
        
    # --- Core Interview Logic ---
    next_question = ""
    next_step_to_save = current_step_name # Default: stay on current step if no valid input

    # Check if this is the first interaction OR if no valid speech was captured
    if not speech_result and current_step_name == "START" and recognition_status == '':
        print(f"First interaction for '{from_number}'. Asking START question.")
        # next_step_to_save remains 'START' as we're about to ask its question
        pass 
    elif recognition_status == 'NoSpeech' or recognition_status == 'Error':
        print(f"No speech or error in recognition. Repeating question for step '{current_step_name}'.")
        resp.say("I didn't hear anything or had trouble understanding. Could you please repeat your answer?")
    elif speech_result:
        print(f"Processing speech result for *previous* step '{current_step_name}'...")
        prev_step_info = get_flow_info(current_step_name)

        if prev_step_info and prev_step_info["field"]:
            try:
                candidate_profile_data = parse_and_update_profile(prev_step_info["field"], speech_result, candidate_profile_data)
                
                # --- Save Candidate Profile to Memory ---
                candidate_profiles[from_number] = candidate_profile_data
                print(f"Saved candidate profile for {from_number} in memory: {candidate_profiles[from_number]}.")
                
                # If parsing and saving were successful, advance to the next step
                next_step_to_save = get_next_step_name(current_step_name)
                
            except Exception as e:
                print(f"Error during parsing or profile update: {e}. Repeating current question.")
                resp.say("I had some trouble understanding that. Could you please repeat your answer?")
        else: 
            print(f"Warning: Speech result received but no field to process for step {current_step_name}. Advancing anyway.")
            next_step_to_save = get_next_step_name(current_step_name)

    # Get the question for the determined next step
    target_step_info = get_flow_info(next_step_to_save)
    if target_step_info:
        next_question = target_step_info["question"]
    else:
        print(f"Error: No flow info found for step: {next_step_to_save}. Ending call.")
        resp.say("An unexpected error occurred. Goodbye!")
        resp.hangup()
        return str(resp)

    # Play the question and gather response
    if next_step_to_save != "END":
        print(f"Asking question for step '{next_step_to_save}': {next_question}")
        # Twilio will wait for timeout seconds for speech. If not found, it sends SpeechResultStatus as NoSpeech.
        with resp.gather(input='speech', timeout=10, action='/voice', method='POST'): # timeout 10 seconds
            resp.say(next_question)
    else:
        print(f"Conversation ending. Final message: {next_question}")
        resp.say(next_question)
        resp.hangup()

    # --- Update Conversation State in Memory ---
    conversation_states[from_number] = {"currentStep": next_step_to_save}
    print(f"Saved conversation state for {from_number} in memory. Next step: {next_step_to_save}")
    print(f"Current candidate_profiles in memory: {candidate_profiles}") # Add this to see all profiles
    print(f"Current conversation_states in memory: {conversation_states}") # Add this to see all states


    return str(resp)

# --- Flask App Lifecycle Hooks ---
# Since no external database, these hooks are simplified.
@app.before_request
def before_first_request_hook():
    print("Flask app starting. No external database connection needed.")
    pass

@app.teardown_appcontext
def teardown_app_context(exception=None):
    # This hook runs after each request is completed.
    # When using in-memory storage, data persists until the Python process is stopped.
    print("Flask app context torn down. In-memory data will persist until app restart.")
    pass

# --- Main Entry Point for Running the Flask App ---
if __name__ == '__main__':
    print("Starting Flask application (using in-memory storage) on port 5000...")
    # This line tells Flask to listen on port 5000
    app.run(host='0.0.0.0', port=8000, debug=True)