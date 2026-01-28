from firebase_admin import firestore

from database import TRACKED_USERS_COLLECTION
from utils.exceptions import DatabaseError
from utils.logger_config import logger


class DatabaseService:
    """Service layer for league specific Firestore operations."""

    def __init__(self, db):
        self.db = db

    # Guild operations

    # Player operations

    async def track_user(self, ctx, riot_id: str, puuid: str, ranked_data):
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        payload = {
            "riot_id": riot_id,
            "puuid": puuid,
            "tier": f"{ranked_data.get('tier')}",
            "rank": f"{ranked_data.get('rank')}",
            "LP": ranked_data.get("LP"),
            "guild_ids": firestore.ArrayUnion([guild_id_str]),
            f"server_info.{guild_id_str}": {"added_by": ctx.author.id},
        }
        try:
            doc_ref.set(payload, merge=True)
        except Exception as e:
            logger.exception(f"❌ ERROR: tracking: {e}")
            await ctx.send("Database update failed")
            raise DatabaseError(f"Database write failed for player {riot_id}") from e

    async def untrack_user(self, ctx, riot_id, puuid):
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        try:
            doc = doc_ref.get()
            if not doc.exists:
                return await ctx.send(f"{riot_id} is not in the database.")
            data = doc.to_dict()
            guild_list = data.get("guild_ids", [])
            if guild_id_str not in guild_list:
                return await ctx.send(f"{riot_id} is not being tracked in this server.")
            guild_list.remove(guild_id_str)
            if not guild_list:
                # We are the only server left, delete the whole file
                doc_ref.delete()
            else:
                data["guild_ids"] = guild_list
                del data[f"server_info.{guild_id_str}"]
                doc_ref.set(data)
        except Exception as e:
            logger.exception(f"❌ ERROR: untracking: {e}")
            await ctx.send("Database update failed")
            raise DatabaseError(f"Database write failed for player {riot_id}") from e
