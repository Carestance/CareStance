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
