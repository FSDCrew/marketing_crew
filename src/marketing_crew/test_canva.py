import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from tools.canva import CanvaTool
import traceback

# Load environment variables from .env file
load_dotenv()

def run_canva_test():
    print("--- [CANVA TOOL TEST STARTED] ---")
    try:
        # Check for keys first
        print("[DEBUG] Checking for environment variables...")
        gemini_key = os.getenv("GEMINI_API_KEY")
        canva_key = os.getenv("CANVA_API_KEY")

        if not gemini_key or not canva_key:
            print("\n[DEBUG] Error: GEMINI_API_KEY or CANVA_API_KEY not found in .env file.")
            if not gemini_key: print("[DEBUG] GEMINI_API_KEY is missing.")
            if not canva_key: print("[DEBUG] CANVA_API_KEY is missing.")
            return
        
        print("[DEBUG] Found GEMINI_API_KEY and CANVA_API_KEY.")

        # --- EXPLICITLY CREATE THE GEMINI LLM ---
        print("[DEBUG] Creating ChatGoogleGenerativeAI object...")
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash-latest",
            temperature=0.1,
            google_api_key=gemini_key
        )
        if llm is None:
            print("[DEBUG] Error: ChatGoogleGenerativeAI object creation FAILED.")
            return
        print(f"[DEBUG] ChatGoogleGenerativeAI object created: {llm}")

        # --- THIS IS THE NEW FIX ---
        # 1. Define the Test Agent WITHOUT the LLM first
        print("[DEBUG] Creating Test Agent (Step 1)...")
        test_designer = Agent(
            role="Canva Test Agent",
            goal="Test the Canva tool with predefined inputs.",
            backstory="I am a test agent designed to trigger the CanvaTool with specific data.",
            tools=[CanvaTool()],
            verbose=True,
            allow_delegation=False
        )
        print("[DEBUG] Test Agent created (without LLM).")

        # 2. Explicitly SET the LLM and trigger setup
        print(f"[DEBUG] Explicitly setting LLM on agent...")
        # test_designer.set_llm(llm)
        
        # This next line manually triggers the internal setup that was failing before
        # test_designer.set_cache_handler(None) 
        
        if test_designer.llm is None:
            print("[DEBUG] CRITICAL ERROR: Agent's LLM is still None after set_llm().")
            return
        else:
            print(f"[DEBUG] Agent's LLM is successfully set: {test_designer.llm}")
        # --- END OF NEW FIX ---


        # 3. Define the Test Task
        print("[DEBUG] Defining Test Task...")
        test_task = Task(
            description=(
                "You must use the `Canva Designer` tool *exactly* as specified.\n"
                "DO NOT change any of the values.\n"
                # IMPORTANT: You must replace this with a real template ID
                "template_id: 'YOUR_TEMPLATE_ID_GOES_HERE'\n" 
                "text_fields: { \"headline\": \"This is a test headline\", \"body\": \"This is test body text.\" }\n"
                "image_fields: { \"product_image_frame\": \"https://placehold.co/600x400/EEE/31343C?text=Test+Image\" }"
            ),
            expected_output=(
                "The full JSON output from the Canva Designer tool, "
                "containing the status and the new design URL."
            ),
            agent=test_designer,
        )
        print("[DEBUG] Test Task defined.")

        # 4. Create and Run the Crew
        print("[DEBUG] Creating Crew...")
        test_crew = Crew(
            agents=[test_designer],
            tasks=[test_task],
            process=Process.sequential,
            verbose=True
            # llm=llm
        )

        print("[DEBUG] Kicking off Crew...")
        result = test_crew.kickoff()

        print("\n--- [CANVA TOOL TEST FINISHED] ---")
        print("Final Result:")
        print(result)

    except Exception as e:
        print(f"An error occurred during the test: {e}")
        print("Please check:")
        print("1. Your .env file has correct GEMINI_API_KEY and CANVA_API_KEY.")
        print("2. You have run 'pip install langchain-google-genai'.")
        print("3. Your canva.py file is in src/marketing_crew/tools/.")
        print("\n--- [FULL ERROR TRACEBACK] ---")
        traceback.print_exc() # Print the full error stack trace

if __name__ == "__main__":
    run_canva_test()

