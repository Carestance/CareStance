import json
from appwrite.query import Query
from .appwrite_client import databases, DB_ID, COLLECTIONS

def doc_to_model(doc, db=None):
    """Converts an Appwrite document to a SimpleNamespace that looks like an SQLAlchemy model."""
    from types import SimpleNamespace
    data = dict(doc)
    
    # SimpleNamespace allows dot-access like user.full_name
    model = SimpleNamespace(**data)
    
    # Lazy-loading-like behavior for common relationships
    if 'id' in data:
        # If it's a User, try to load assessment
        if 'email' in data: 
             model.assessment = get_assessment_by_user_id(data['id'])
        
        # If it's an assessment result, unpack consolidated JSON blobs
        if 'simulation_data' in data and data['simulation_data']:
            try:
                sim_json = json.loads(data['simulation_data'])
                model.simulation_career = sim_json.get('career')
                model.simulation_questions = sim_json.get('questions')
                model.simulation_answers = sim_json.get('answers')
                model.simulation_evaluation = sim_json.get('evaluation')
            except: pass
    
    return model

def get_assessment_by_user_id(user_num_id):
    """Fetches assessment result for a user from Appwrite."""
    try:
        res = databases.list_documents(
            DB_ID, 
            COLLECTIONS['assessment_results'], 
            [Query.equal('user_id', int(user_num_id))]
        )
        if res['total'] > 0:
            return SimpleNamespace(**res['documents'][0])
    except:
        pass
    return None

def update_assessment_simulation(user_num_id, career=None, questions=None, answers=None, evaluation=None):
    """Updates simulation data for a user in Appwrite."""
    try:
        # 1. Find the document
        res = databases.list_documents(
            DB_ID, 
            COLLECTIONS['assessment_results'], 
            [Query.equal('user_id', int(user_num_id))]
        )
        if res['total'] == 0: return False
        
        doc_id = res['documents'][0]['$id']
        current_data_str = res['documents'][0].get('simulation_data', '{}')
        try:
            sim_data = json.loads(current_data_str) if current_data_str else {}
        except:
            sim_data = {}
        
        # 2. Update fields
        if career is not None: sim_data['career'] = career
        if questions is not None: sim_data['questions'] = questions
        if answers is not None: sim_data['answers'] = answers
        if evaluation is not None: sim_data['evaluation'] = evaluation
        
        # 3. Save back
        databases.update_document(
            DB_ID,
            COLLECTIONS['assessment_results'],
            doc_id,
            {'simulation_data': json.dumps(sim_data)}
        )
        return True
    except Exception as e:
        print(f"Appwrite Update Simulation Error: {e}")
    return False

def get_user_by_id(user_num_id):
    """Fetches a user from Appwrite users collection by their numeric local_id."""
    try:
        res = databases.list_documents(
            DB_ID, 
            COLLECTIONS['users'], 
            [Query.equal('id', int(user_num_id))]
        )
        if res['total'] > 0:
            return doc_to_model(res['documents'][0])
    except Exception as e:
        print(f"Appwrite Get User Error: {e}")
    return None

def get_user_by_email(email):
    """Fetches a user from Appwrite users collection by email."""
    try:
        res = databases.list_documents(
            DB_ID, 
            COLLECTIONS['users'], 
            [Query.equal('email', email)]
        )
        if res['total'] > 0:
            return doc_to_model(res['documents'][0])
    except Exception as e:
        print(f"Appwrite Get User Email Error: {e}")
    return None

def sync_assessment_to_appwrite(user_num_id, result):
    """Syncs assessment results from Supabase/PostgreSQL to Appwrite.
    Uses list_attributes to dynamically filter payload keys to only those
    supported by the Appwrite collection, avoiding schema conflicts.
    """
    try:
        import json
        from appwrite.query import Query
        
        # 1. Fetch available attributes from Appwrite collection
        try:
            res_attrs = databases.list_attributes(DB_ID, COLLECTIONS['assessment_results'])
            attrs = getattr(res_attrs, 'attributes', []) if not isinstance(res_attrs, dict) else res_attrs.get('attributes', [])
            available_keys = {attr.get('key') for attr in attrs if attr.get('status') == 'available'}
        except Exception as attr_e:
            print(f"Appwrite Sync: Could not list attributes (likely project paused): {attr_e}")
            # Fallback to a safe minimum of commonly supported attributes
            available_keys = {"user_id", "selected_class", "student_type", "personality", "confidence", "goal_status"}
            
        # 2. Build the payload dynamically based on local result object
        payload = {}
        
        # Map values with appropriate serialization
        for field in [
            "user_id", "selected_class", "student_type", "current_phase", "intake_turn",
            "intake_name", "intake_grade", "intake_stream", "chat_turn", "personality",
            "goal_status", "confidence", "reasoning", "phase_2_category", "phase3_result",
            "phase3_analysis", "recommended_stream", "final_analysis"
        ]:
            val = getattr(result, field, None)
            if val is not None:
                payload[field] = val
                
        # Handle JSON fields (serialize to string since Appwrite stores them as String attributes or text)
        for json_field in [
            "telemetry_logs", "reality_answers", "chat_messages", "proxy_answers",
            "scenario_answers", "worldview_answers", "future_self_answers",
            "assessment_report", "raw_answers", "phase3_answers", "final_answers",
            "stream_scores", "stream_pros", "stream_cons"
        ]:
            val = getattr(result, json_field, None)
            if val is not None:
                payload[json_field] = json.dumps(val)
                
        # Filter payload to only keys present in available_keys
        filtered_payload = {k: v for k, v in payload.items() if k in available_keys}
        
        # Ensure user_id is set
        if "user_id" in available_keys:
            filtered_payload["user_id"] = int(user_num_id)
            
        if not filtered_payload:
            print("Appwrite Sync: No matching attributes found to sync.")
            return False
            
        # 3. Check if document already exists
        res = databases.list_documents(
            DB_ID,
            COLLECTIONS['assessment_results'],
            [Query.equal('user_id', int(user_num_id))]
        )
        
        if res['total'] > 0:
            doc_id = res['documents'][0]['$id']
            databases.update_document(
                DB_ID,
                COLLECTIONS['assessment_results'],
                doc_id,
                filtered_payload
            )
            print(f"Appwrite Sync: Updated assessment for user {user_num_id}")
        else:
            doc_uuid = f"ar_{user_num_id}" # Predictable unique doc ID
            databases.create_document(
                DB_ID,
                COLLECTIONS['assessment_results'],
                doc_uuid,
                filtered_payload
            )
            print(f"Appwrite Sync: Created assessment for user {user_num_id}")
            
        return True
    except Exception as e:
        print(f"Appwrite Sync Assessment Error (Non-blocking): {e}")
        return False
