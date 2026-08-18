from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import AssessmentResult, User
import json

class ContextLoader:
    """Loads assessment context without mutating the application state."""
    
    @staticmethod
    async def load_user_context(user_id: Optional[int], db: AsyncSession) -> Dict[str, Any]:
        """Fetches read-only user and assessment context for the LLM prompt."""
        if not user_id:
            return {
                "name": "Guest", 
                "grade": "Unknown", 
                "archetype": "Unknown", 
                "recommended_path": "Not determined yet"
            }
            
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalars().first()
        
        if not user:
            return {
                "name": "Guest", 
                "grade": "Unknown", 
                "archetype": "Unknown", 
                "recommended_path": "Not determined yet"
            }
            
        assess_stmt = select(AssessmentResult).where(AssessmentResult.user_id == user_id)
        assess_res = await db.execute(assess_stmt)
        result = assess_res.scalars().first()
        
        context_data = {
            "name": user.full_name or "Student",
            "grade": "Unknown",
            "archetype": "Unknown",
            "recommended_path": "Not determined yet"
        }
        
        if result:
            context_data["grade"] = result.selected_class or "Unknown"
            context_data["archetype"] = result.phase_2_category or "Unknown"
            context_data["recommended_path"] = result.recommended_stream or "Not determined yet"
            
            # Extract basic phase 1 interests safely
            if result.raw_answers and isinstance(result.raw_answers, dict):
                context_data["interests"] = result.raw_answers.get("interests", [])
                
        return context_data
