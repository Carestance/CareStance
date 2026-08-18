from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import ConversationSummary
import datetime

class MemoryRepository:
    """Handles persistent storage of conversation summaries."""
    
    @staticmethod
    async def get_summary(client_id: str, db: AsyncSession) -> Optional[str]:
        """Fetches the existing summary for a given client."""
        stmt = select(ConversationSummary).where(ConversationSummary.client_id == client_id)
        result = await db.execute(stmt)
        record = result.scalars().first()
        return record.summary_text if record else None

    @staticmethod
    async def update_summary(client_id: str, user_id: Optional[int], new_summary: str, db: AsyncSession) -> None:
        """Upserts the conversation summary asynchronously."""
        stmt = select(ConversationSummary).where(ConversationSummary.client_id == client_id)
        result = await db.execute(stmt)
        record = result.scalars().first()
        
        if record:
            record.summary_text = new_summary
            record.last_updated = datetime.datetime.now(datetime.timezone.utc)
            if user_id:
                record.user_id = user_id
        else:
            record = ConversationSummary(
                client_id=client_id,
                user_id=user_id,
                summary_text=new_summary,
                last_updated=datetime.datetime.now(datetime.timezone.utc)
            )
            db.add(record)
            
        await db.commit()
