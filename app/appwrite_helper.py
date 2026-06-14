import json
from appwrite.query import Query
from .appwrite_client import databases, DB_ID, COLLECTIONS

def _parse_list_response(res):
    """Safely extracts total and documents list from Appwrite list response."""
    total = getattr(res, 'total', 0) if not isinstance(res, dict) else res.get('total', 0)
    documents = getattr(res, 'documents', []) if not isinstance(res, dict) else res.get('documents', [])
    return total, documents

def doc_to_model(doc, db=None):
    """Converts an Appwrite document to a SimpleNamespace that looks like an SQLAlchemy model."""
    from types import SimpleNamespace
    import json
    
    # 1. Get base metadata attributes
    if hasattr(doc, 'to_dict'):
        data = doc.to_dict()
    else:
        data = dict(doc)
        
    # 2. Extract internal data dictionary if present (Appwrite SDK houses attributes under 'data')
    if 'data' in data and isinstance(data['data'], dict):
        # Merge properties inside data to top-level
        inner_data = data.pop('data')
        data.update(inner_data)
        
    # 3. Standardize '$id' and 'id' to map Appwrite document id or numeric local_id appropriately
    if '$id' in data:
        data['appwrite_id'] = data['$id']
        
    # For a User, the database ID used throughout the app is the numeric local_id
    if 'local_id' in data and data['local_id'] is not None:
        data['id'] = int(data['local_id'])
    elif '$id' in data and 'id' not in data:
        # Fallback to Appwrite document ID if no local_id (e.g. for non-user collections)
        data['id'] = data['$id']

    model = SimpleNamespace(**data)
    
    # Lazy-loading-like behavior for common relationships
    if 'id' in data:
        # If it's a User (has email attribute), try to load assessment
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
        total, documents = _parse_list_response(res)
        if total > 0:
            return doc_to_model(documents[0])
    except Exception as e:
        print(f"Appwrite Get Assessment Error: {e}")
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
        total, documents = _parse_list_response(res)
        if total == 0: return False
        
        doc = documents[0]
        # Get Appwrite document ID (either doc.id or doc_dict['$id'])
        doc_id = getattr(doc, 'id', None) or dict(doc).get('$id')
        
        current_data_str = doc.data.get('simulation_data', '{}') if hasattr(doc, 'data') else dict(doc).get('simulation_data', '{}')
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
            [Query.equal('local_id', int(user_num_id))]
        )
        total, documents = _parse_list_response(res)
        if total > 0:
            return doc_to_model(documents[0])
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
        total, documents = _parse_list_response(res)
        if total > 0:
            return doc_to_model(documents[0])
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
            "telemetry_logs", "chat_messages", "proxy_answers",
            "scenario_answers", "assessment_report", "raw_answers",
            "phase3_answers", "final_answers", "stream_scores",
            "stream_pros", "stream_cons"
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
        total, documents = _parse_list_response(res)
        
        if total > 0:
            doc = documents[0]
            doc_id = getattr(doc, 'id', None) or dict(doc).get('$id')
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
