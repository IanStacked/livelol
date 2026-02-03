from firebase_admin import firestore
from google.cloud.firestore import FieldFilter

from database import GUILD_CONFIG_COLLECTION, TRACKED_USERS_COLLECTION
from utils.exceptions import DatabaseError, UserNotFoundError
from utils.logger_config import logger


class DatabaseService:
    """Service layer for league specific Firestore operations."""

    def __init__(self, db):
        self.db = db

    # Guild operations

    async def set_guild_config(self, ctx):
        doc_ref = (
            self.bot.db.collection(GUILD_CONFIG_COLLECTION).document(str(ctx.guild.id))
        )
        doc_ref.set({"channel_id": ctx.channel.id}, merge=True)

    async def remove_guild_config(self, guild):
        try:
            doc_ref = (
            self.db.collection(GUILD_CONFIG_COLLECTION).document(str(guild.id))
            )
            if doc_ref is None:
                # File was never created
                return
            doc_ref.delete()
        except Exception as e:
            logger.exception(f"❌ ERROR: failed to delete guild config {guild.id}")
            raise DatabaseError(
                f"Database operation failed for guild {guild.id}: {e}",
                ) from e


    # Player operations

    async def untrack_all_users(self, guild):
        try:
            guild_id_str = str(guild.id)
            docs = (
                self.db.collection(TRACKED_USERS_COLLECTION)
                .where(filter=FieldFilter("guild_ids", "array_contains", guild_id_str))
                .stream()
            )
            doc_list = list(docs)
            if not doc_list:
                # No users tracked in server
                return
            for doc in doc_list:
                doc_ref = doc.reference
                data = doc.to_dict()
                guild_list = data.get("guild_ids", [])
                guild_list.remove(guild_id_str)
                if not guild_list:
                    # We were the only server left, delete the whole user file
                    doc_ref.delete()
                else:
                    data["guild_ids"] = guild_list
                    del data[f"server_info.{guild_id_str}"]
                    doc_ref.set(data)
        except Exception as e:
            logger.exception(
                f"❌ ERROR: failed to untrack all users from guild {guild.id} : {e}",
            )
            raise DatabaseError(
                f"Database operation failed for guild {guild.id}: {e}",
                ) from e


    async def track_user(self, ctx, riot_id: str, puuid: str, ranked_data, region):
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        payload = {
            "riot_id": riot_id,
            "puuid": puuid,
            "region": region,
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
            raise DatabaseError(f"Database write failed for player {riot_id}.") from e

    async def untrack_user(self, ctx, riot_id, puuid):
        guild_id_str = str(ctx.guild.id)
        doc_id = puuid
        doc_ref = self.db.collection(TRACKED_USERS_COLLECTION).document(doc_id)
        try:
            doc = doc_ref.get()
            if not doc.exists:
                raise UserNotFoundError(
                    f"{riot_id} is not being tracked.",
                )
            data = doc.to_dict()
            guild_list = data.get("guild_ids", [])
            if guild_id_str not in guild_list:
                raise UserNotFoundError(
                    f"{riot_id} is not being tracked in this server.",
                )
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
            raise DatabaseError(f"Database write failed for player {riot_id}.") from e
