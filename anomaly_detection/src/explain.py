import os
import time
from google import genai

def explain_anomalies_with_gemini(results, api_key=None):
    """
    Optional Gemini explanation layer.
    Translates a flagged row's numeric reason into a single plain-language sentence.
    Uses gemini-2.5-pro as primary, falling back sequentially to gemini-2.5-flash,
    gemini-1.5-pro, and gemini-1.5-flash if errors/quota issues occur.
    Implements retries with exponential backoff on rate limits (429/RESOURCE_EXHAUSTED).
    """
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
        
    if not api_key:
        # Fallback: if no key is present, we populate explanations with empty strings
        for r in results:
            r["explanation"] = ""
        return results

    # Fallback model list
    models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

    try:
        client = genai.Client(api_key=api_key)
        active_model_idx = 0  # Keep track of the current working model
        
        for r in results:
            if r["score"] > 0 and len(r["flags"]) > 0:
                flags_text = ""
                for f in r["flags"]:
                    flags_text += f"- Rule '{f['rule']}' failed: {f}\n"

                prompt = (
                    "You are a rental equipment operations assistant. A machine has been flagged for operational anomalies.\n"
                    f"Equipment ID: {r['Equipment_ID']}\n"
                    f"Equipment Type: {r['Type']}\n"
                    f"Telemetry/Flags:\n{flags_text}\n"
                    "Write exactly one concise, plain-language sentence explaining the operational reason or issue for these flags to a fleet manager.\n"
                    "Do not include any greeting, conversational filler, or markdown formatting. Return ONLY the raw explanation sentence."
                )

                # Attempt with fallback chain and retries on 429
                explanation = ""
                success = False
                
                for i in range(len(models)):
                    idx = (active_model_idx + i) % len(models)
                    model_name = models[idx]
                    
                    # Try up to 3 times with a longer delay to let the RPM rate limits reset
                    max_retries = 3
                    delay = 40.0
                    model_success = False
                    
                    for attempt in range(max_retries):
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt
                            )
                            explanation = str(response.text).strip()
                            model_success = True
                            success = True
                            active_model_idx = idx  # Keep using this model as it works
                            break
                        except Exception as ex:
                            err_str = str(ex).lower()
                            # Check if it is a rate limit or resource exhausted error
                            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "limit" in err_str:
                                if attempt < max_retries - 1:
                                    print(f"Model '{model_name}' hit rate limit (attempt {attempt+1}/{max_retries}). Waiting {delay}s for window to reset...")
                                    time.sleep(delay)
                                    # Keep delay at 40s to ensure window resets
                                    continue
                            # If it's a 404 or other fatal error, or we're out of retries, fail this model and try next model in fallback list
                            print(f"Model '{model_name}' call failed on attempt {attempt+1}: {ex}")
                            break
                            
                    if model_success:
                        break
                    else:
                        print(f"Model '{model_name}' failed all retries or encountered fatal error. Trying next fallback...")

                if not success:
                    print("All Gemini models in the fallback chain failed.")
                    r["explanation"] = ""
                else:
                    r["explanation"] = explanation
            else:
                r["explanation"] = ""
    except Exception as e:
        print(f"Error initializing Gemini API Client or processing: {e}")
        # fallback to empty string
        for r in results:
            if "explanation" not in r:
                r["explanation"] = ""
                
    return results
