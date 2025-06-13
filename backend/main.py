import os
import time
import json
import re
import weaviate
import datetime # Still needed for other potential date uses, but not for updatedAt
from weaviate.classes.query import Filter 

# Debug prints for module and version loaded
print(f"DEBUG: weaviate module loaded from: {weaviate.__file__}")
print(f"DEBUG: weaviate-client version loaded: {weaviate.__version__}") 

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
WEAVIATE_URL = "http://localhost:8080" # Standard local Weaviate URL
CANDIDATE_PROFILE_COLLECTION_NAME = "CandidateProfile"
CONVERSATION_STATE_COLLECTION_NAME = "ConversationState"

# Twilio Credentials (from .env)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# OpenAI Client (from .env)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
LLM_MODEL = "gpt-4o-mini" # A cost-effective and capable model

# --- Flask App Initialization ---
app = Flask(__name__)

# Global Weaviate client instance
weaviate_client = None

# --- Weaviate Connection and Schema Setup ---
def init_weaviate_client():
    """Initializes the Weaviate client and waits for it to be ready."""
    global weaviate_client
    print("Attempting to connect to Weaviate using weaviate.connect_to_local (v4 syntax)...")
    for i in range(5): # Try connecting a few times with a delay
        try:
            weaviate_client = weaviate.connect_to_local(port=8080)
            if weaviate_client.is_connected():
                print("✅ Successfully connected to Weaviate!")
                print(f"Weaviate server version: {weaviate_client.get_meta()['version']}")
                return True
            else:
                print(f"Attempt {i+1}: Weaviate client not connected. Retrying in 3 seconds...")
                time.sleep(3)
        except Exception as e:
            print(f"Attempt {i+1}: Error connecting to Weaviate: {e}. Retrying in 3 seconds...")
            time.sleep(3)
    print("❌ Failed to connect to Weaviate. Ensure Docker container is running and accessible on port 8080.")
    return False

def setup_weaviate_schemas():
    """
    Ensures 'CandidateProfile' and 'ConversationState' schemas exist.
    Will delete existing ones to ensure clean schema definition.
    """
    if not weaviate_client or not weaviate_client.is_connected():
        print("Weaviate client not connected. Cannot setup schemas.")
        return

    # --- CandidateProfile Schema ---
    print(f"\n--- Ensuring '{CANDIDATE_PROFILE_COLLECTION_NAME}' schema exists ---")
    profile_properties = [
        weaviate.classes.config.Property(name="phoneNumber", data_type=weaviate.classes.config.DataType.TEXT, description="Candidate's phone number", skip_vectorization=True),
        weaviate.classes.config.Property(name="javaExperience", data_type=weaviate.classes.config.DataType.TEXT, description="Candidate's Java experience summary", skip_vectorization=True),
        weaviate.classes.config.Property(name="expectedSalary", data_type=weaviate.classes.config.DataType.TEXT, description="Candidate's expected salary", skip_vectorization=True),
        weaviate.classes.config.Property(name="availableTimeSlots", data_type=weaviate.classes.config.DataType.TEXT, description="Candidate's preferred interview time slot", skip_vectorization=True)
        # Removed 'updatedAt' field
    ]
    try:
        # Force schema deletion for clean slate if it exists
        if weaviate_client.collections.exists(CANDIDATE_PROFILE_COLLECTION_NAME):
            print(f"🗑️ Deleting existing '{CANDIDATE_PROFILE_COLLECTION_NAME}' schema to ensure correct definition.")
            weaviate_client.collections.delete(CANDIDATE_PROFILE_COLLECTION_NAME)
        
        print(f"Collection '{CANDIDATE_PROFILE_COLLECTION_NAME}' does not exist. Attempting to create it...")
        weaviate_client.collections.create(
            name=CANDIDATE_PROFILE_COLLECTION_NAME,
            properties=profile_properties
        )
        print(f"✅ Created '{CANDIDATE_PROFILE_COLLECTION_NAME}' schema.")
        time.sleep(1) # Small delay after creation for propagation
    except Exception as e:
        print(f"❌ Error creating/checking '{CANDIDATE_PROFILE_COLLECTION_NAME}' schema: {e}")
        raise

    # --- ConversationState Schema ---
    print(f"\n--- Ensuring '{CONVERSATION_STATE_COLLECTION_NAME}' schema exists ---")
    state_properties = [
        weaviate.classes.config.Property(name="phoneNumber", data_type=weaviate.classes.config.DataType.TEXT, description="Candidate's phone number", is_required=True, skip_vectorization=True),
        weaviate.classes.config.Property(name="currentStep", data_type=weaviate.classes.config.DataType.TEXT, description="Current step in the interview flow", skip_vectorization=True)
        # Removed 'updatedAt' field
    ]
    try:
        # Force schema deletion for clean slate if it exists
        if weaviate_client.collections.exists(CONVERSATION_STATE_COLLECTION_NAME):
            print(f"🗑️ Deleting existing '{CONVERSATION_STATE_COLLECTION_NAME}' schema to ensure correct definition.")
            weaviate_client.collections.delete(CONVERSATION_STATE_COLLECTION_NAME)

        print(f"Collection '{CONVERSATION_STATE_COLLECTION_NAME}' does not exist. Attempting to create it...")
        weaviate_client.collections.create(
            name=CONVERSATION_STATE_COLLECTION_NAME,
            properties=state_properties
        )
        print(f"✅ Created '{CONVERSATION_STATE_COLLECTION_NAME}' schema.")
        time.sleep(1) # Small delay after creation for propagation
    except Exception as e:
        print(f"❌ Error creating/checking '{CONVERSATION_STATE_COLLECTION_NAME}' schema: {e}")
        raise

# --- Interview Flow Definition ---
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
    return None # Should not happen if flow is well-defined

def get_next_step_name(current_step_name: str):
    """Determines the name of the next step in the interview flow."""
    for i, step_info in enumerate(interview_flow_config):
        if step_info["step"] == current_step_name:
            if i + 1 < len(interview_flow_config):
                return interview_flow_config[i + 1]["step"]
    return "END" # If no next step, it's the end

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
        The user was offered interview slots on 'Monday at 2 PM', 'Tuesday at 10 AM', and 'Wednesday at 4 PM'.
        Based on their response, identify which of these slots they preferred.
        User response: '{user_response}'
        Respond with only the chosen slot (e.g., 'Tuesday at 10 AM'). If multiple or none are chosen, pick the clearest single option or respond 'No specific slot chosen'.
        """
        llm_response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        extracted_value = llm_response if llm_response and llm_response.lower() != "no specific slot chosen" else "No specific slot chosen"
    
    # Update the profile dictionary with the extracted value
    candidate_profile[field] = extracted_value
    print(f"Updated candidate profile for field '{field}': {extracted_value}")
    return candidate_profile

# --- Flask API Endpoint for Twilio Voice Webhook ---
@app.route("/voice", methods=['POST'])
def voice_interview():
    """Handles incoming voice calls from Twilio."""
    from_number = request.form['From']
    # If using <Gather>, the ASR transcription is in 'SpeechResult'
    speech_result = request.form.get('SpeechResult', '').strip()
    
    print(f"\n--- Incoming Call from: {from_number} ---")
    print(f"SpeechResult (if any): '{speech_result}'")

    resp = VoiceResponse()
    profile_collection = weaviate_client.collections.get(CANDIDATE_PROFILE_COLLECTION_NAME)
    state_collection = weaviate_client.collections.get(CONVERSATION_STATE_COLLECTION_NAME)

    current_step_name = "START" # Default for new calls or initial webhook
    candidate_profile_data = {"phoneNumber": from_number}
    candidate_profile_uuid = None
    state_object_uuid = None

    try:
        # Retrieve or Initialize Conversation State
        state_results = state_collection.query.fetch_objects(
            filters=Filter.by_property("phoneNumber").equal(from_number),
            limit=1
        )
        if state_results.objects:
            state_object_uuid = state_results.objects[0].uuid
            current_step_name = state_results.objects[0].properties["currentStep"]
            print(f"Existing state for {from_number}. Loaded step: {current_step_name}")
        else:
            print(f"New call from {from_number}. Initial step: {current_step_name}")

        # Retrieve or Initialize Candidate Profile
        profile_results = profile_collection.query.fetch_objects(
            filters=Filter.by_property("phoneNumber").equal(from_number),
            limit=1
        )
        if profile_results.objects:
            candidate_profile_uuid = profile_results.objects[0].uuid
            # Ensure all properties are loaded, convert to a mutable dict if it's a Weaviate DataObject
            candidate_profile_data = dict(profile_results.objects[0].properties)
            print(f"Existing candidate profile found for {from_number}: {candidate_profile_data}")
        else:
            print(f"New candidate profile for {from_number}. Will be created on first data capture.")

    except Exception as e:
        print(f"Error during initial state/profile retrieval: {e}")
        resp.say("I am having trouble connecting to my systems. Please try again later. Goodbye.")
        return str(resp)

    # --- Core Interview Logic ---
    next_question = ""
    next_step_to_save = current_step_name 

    if speech_result:
        print(f"Processing speech result for *previous* step '{current_step_name}'...")
        prev_step_info = get_flow_info(current_step_name)

        if prev_step_info and prev_step_info["field"]:
            try:
                candidate_profile_data = parse_and_update_profile(prev_step_info["field"], speech_result, candidate_profile_data)
                # Removed: candidate_profile_data["updatedAt"] = ...

                if candidate_profile_uuid:
                    profile_collection.data.update(
                        uuid=candidate_profile_uuid,
                        properties=candidate_profile_data
                    )
                    print(f"Updated candidate profile (UUID: {candidate_profile_uuid}).")
                else:
                    candidate_profile_uuid = profile_collection.data.insert(properties=candidate_profile_data)
                    print(f"Created new candidate profile (UUID: {candidate_profile_uuid}).")
                
                next_step_to_save = get_next_step_name(current_step_name)
                
            except Exception as e:
                print(f"Error during parsing or profile update: {e}. Repeating current question.")
                resp.say("I had some trouble understanding that. Could you please repeat your answer?")
        else: 
            print(f"Warning: Speech result received but no field to process for step {current_step_name}. Advancing anyway.")
            next_step_to_save = get_next_step_name(current_step_name)
    else: 
        print(f"No speech result found, assuming initial call or retry for step '{current_step_name}'.")

    target_step_info = get_flow_info(next_step_to_save)
    if target_step_info:
        next_question = target_step_info["question"]
    else:
        print(f"Error: No flow info found for step: {next_step_to_save}. Ending call.")
        resp.say("An unexpected error occurred. Goodbye!")
        resp.hangup()
        return str(resp)

    if next_step_to_save != "END":
        print(f"Asking question for step '{next_step_to_save}': {next_question}")
        with resp.gather(input='speech', timeout=5, action='/voice', method='POST'):
            resp.say(next_question)
    else:
        print(f"Conversation ending. Final message: {next_question}")
        resp.say(next_question)
        resp.hangup()

    # Update conversation state for the next turn
    new_state_data = {
        "phoneNumber": from_number,
        "currentStep": next_step_to_save,
        # Removed: "updatedAt": ...
    }
    try:
        if state_object_uuid:
            state_collection.data.update(
                uuid=state_object_uuid,
                properties=new_state_data
            )
            print(f"Updated conversation state (UUID: {state_object_uuid}). Saved next step: {next_step_to_save}")
        else:
            state_collection.data.insert(properties=new_state_data)
            print(f"Created new conversation state. Saved next step: {next_step_to_save}")
    except Exception as e:
        print(f"Error saving conversation state for {from_number}: {e}")
        pass

    return str(resp)

# --- Flask App Lifecycle Hooks ---
@app.before_request
def before_first_request_hook():
    global weaviate_client
    if weaviate_client is None or not weaviate_client.is_connected():
        print("Running before_first_request_hook: Weaviate client not connected. Attempting initialization...")
        if init_weaviate_client():
            try:
                setup_weaviate_schemas()
            except Exception as e:
                print(f"❌ Critical error during Weaviate schema setup in before_request: {e}")
                os._exit(1)
        else:
            print("❌ Application cannot start without a successful Weaviate connection (from before_request).")
            os._exit(1)

@app.teardown_appcontext
def teardown_weaviate_client(exception=None):
    global weaviate_client
    if weaviate_client and weaviate_client.is_connected():
        weaviate_client.close()
        print("✅ Weaviate client closed on app teardown.")

# --- Main Entry Point for Running the Flask App ---
if __name__ == '__main__':
    print("Starting Flask application...")
    if init_weaviate_client():
        try:
            setup_weaviate_schemas()
            print("--- Weaviate connected and schemas setup. Starting Flask app. ---")
            app.run(host='0.0.0.0', port=5000, debug=True)
        except Exception as e:
            print(f"❌ Application setup failed due to Weaviate schema error: {e}")
            exit(1)
    else:
        print("❌ Application cannot start without a successful Weaviate connection.")
        exit(1)