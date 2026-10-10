"""PLAT-23: additive discussion identities and immutable message version ancestry."""
import django.db.models.deletion
from django.db import migrations,models

THREAD_SCHEMA={
 "$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
 "properties":{"scope":{"enum":["public","internal"]},
               "kind":{"enum":["feedback","question","idea","request","discussion"]},
               "description":{"type":"string","maxLength":4000}},
 "required":["scope","kind"],"additionalProperties":True,
}
MESSAGE_SCHEMA={
 "$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
 "properties":{"body":{"type":"string","minLength":1,"maxLength":16000},
               "visibility":{"enum":["public","internal"]},
               "edit_reason":{"type":"string","maxLength":4000}},
 "required":["body","visibility"],"additionalProperties":True,
}

def register(apps,editor):
    schema=apps.get_model("config","ObjectTypeVersion")
    schema.objects.using(editor.connection.alias).create(
        type_slug="discussion_thread",version=1,json_schema=THREAD_SCHEMA)
    schema.objects.using(editor.connection.alias).create(
        type_slug="discussion_message",version=1,json_schema=MESSAGE_SCHEMA)

GUARDS="""
CREATE FUNCTION ai_compass_discussion_thread_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM config_catalogitem WHERE id=NEW.item_id
    AND type_slug='discussion_thread') THEN
   RAISE EXCEPTION 'Invalid discussion thread catalog type'; END IF;
 IF (NEW.context_item_id IS NULL)<>(NEW.context_revision_id IS NULL) THEN
   RAISE EXCEPTION 'Discussion context item/revision must be pinned together'; END IF;
 IF NEW.context_item_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM config_catalogrevision
   WHERE id=NEW.context_revision_id AND item_id=NEW.context_item_id
 ) THEN RAISE EXCEPTION 'Invalid exact discussion context revision'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_discussion_thread BEFORE INSERT ON config_discussionthread
 FOR EACH ROW EXECUTE FUNCTION ai_compass_discussion_thread_check();

CREATE FUNCTION ai_compass_discussion_message_check() RETURNS trigger LANGUAGE plpgsql AS $body$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM config_catalogitem WHERE id=NEW.item_id
    AND type_slug='discussion_message') THEN
   RAISE EXCEPTION 'Invalid discussion message catalog type'; END IF;
 IF NEW.parent_id IS NOT NULL AND NOT EXISTS (
   SELECT 1 FROM config_discussionmessage p
   WHERE p.item_id=NEW.parent_id AND p.thread_id=NEW.thread_id
 ) THEN RAISE EXCEPTION 'Discussion reply must belong to same thread'; END IF;
 RETURN NEW;
END $body$;
CREATE TRIGGER valid_discussion_message BEFORE INSERT ON config_discussionmessage
 FOR EACH ROW EXECUTE FUNCTION ai_compass_discussion_message_check();

CREATE TRIGGER immutable_discussion_thread BEFORE UPDATE OR DELETE ON config_discussionthread
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
CREATE TRIGGER immutable_discussion_message BEFORE UPDATE OR DELETE ON config_discussionmessage
 FOR EACH ROW EXECUTE FUNCTION ai_compass_no_revision_mutation();
"""
UNDO="""
DROP TRIGGER IF EXISTS immutable_discussion_message ON config_discussionmessage;
DROP TRIGGER IF EXISTS immutable_discussion_thread ON config_discussionthread;
DROP TRIGGER IF EXISTS valid_discussion_message ON config_discussionmessage;
DROP TRIGGER IF EXISTS valid_discussion_thread ON config_discussionthread;
DROP FUNCTION IF EXISTS ai_compass_discussion_message_check();
DROP FUNCTION IF EXISTS ai_compass_discussion_thread_check();
"""
protect=django.db.models.deletion.PROTECT
class Migration(migrations.Migration):
 dependencies=[("config","0019_recommendations")]
 operations=[
  migrations.RunPython(register,migrations.RunPython.noop),
  migrations.CreateModel(name="DiscussionThread",fields=[
   ("item",models.OneToOneField(to="config.catalogitem",primary_key=True,serialize=False,
                                related_name="discussion_thread",on_delete=protect)),
   ("context_item",models.ForeignKey(to="config.catalogitem",null=True,blank=True,
                                     related_name="+",on_delete=protect)),
   ("context_revision",models.ForeignKey(to="config.catalogrevision",null=True,blank=True,
                                         related_name="+",on_delete=protect)),
  ]),
  migrations.CreateModel(name="DiscussionMessage",fields=[
   ("item",models.OneToOneField(to="config.catalogitem",primary_key=True,serialize=False,
                                related_name="discussion_message",on_delete=protect)),
   ("thread",models.ForeignKey(to="config.discussionthread",related_name="messages",
                               on_delete=protect)),
   ("parent",models.ForeignKey(to="config.discussionmessage",null=True,blank=True,
                               related_name="replies",on_delete=protect)),
  ]),
  migrations.RunSQL(GUARDS,reverse_sql=UNDO),
 ]
