
import logging
import flask

from eve.methods.post import post_internal
from superdesk.notification import push_notification
from superdesk.models import BaseModel


log = logging.getLogger(__name__)


def init_app(app):
    auditModel = AuditModel(app=app)
    app.on_inserted += auditModel.on_generic_inserted
    app.on_updated += auditModel.on_generic_updated
    app.on_deleted_item += auditModel.on_generic_deleted

    ActivityModel(app=app)


class AuditModel(BaseModel):
    endpoint_name = 'audit'
    resource_methods = ['GET']
    item_methods = ['GET']
    schema = {
        'resource': {'type': 'string'},
        'action': {'type': 'string'},
        'extra': {'type': 'dict'},
        'user': BaseModel.rel('users', False)
    }
    exclude = {endpoint_name, 'activity'}

    def on_generic_inserted(self, resource, docs):
        if resource in self.exclude:
            return

        user = getattr(flask.g, 'user', None)
        if not user:
            return

        if not len(docs):
            return

        audit = {
            'user': user.get('_id'),
            'resource': resource,
            'action': 'created',
            'extra': docs[0]
        }

        post_internal(self.endpoint_name, audit)

    def on_generic_updated(self, resource, doc, original):
        if resource in self.exclude:
            return

        user = getattr(flask.g, 'user', None)
        if not user:
            return

        audit = {
            'user': user.get('_id'),
            'resource': resource,
            'action': 'updated',
            'extra': doc
        }
        post_internal(self.endpoint_name, audit)

    def on_generic_deleted(self, resource, doc):
        if resource in self.exclude:
            return

        user = getattr(flask.g, 'user', None)
        if not user:
            return

        audit = {
            'user': user.get('_id'),
            'resource': resource,
            'action': 'deleted',
            'extra': doc
        }
        post_internal(self.endpoint_name, audit)


class ActivityModel(BaseModel):
    endpoint_name = 'activity'
    resource_methods = ['GET']
    item_methods = ['GET', 'PATCH']
    schema = {
        'message': {'type': 'string'},
        'data': {'type': 'dict'},
        'read': {'type': 'dict'},
        'item': BaseModel.rel('archive', type='string'),
        'user': BaseModel.rel('users'),
    }
    exclude = {endpoint_name, 'notification'}
    datasource = {
        'default_sort': [('_created', -1)]
    }


def add_activity(msg, item=None, notify=None, **data):
    """Add an activity into activity log.

    This will became part of current user activity log.

    If there is someone set to be notified it will make it into his notifications box.
    """
    activity = {
        'message': msg,
        'data': data,
    }

    user = getattr(flask.g, 'user', None)
    if user:
        activity['user'] = user.get('_id')

    if notify:
        activity['read'] = {str(_id): 0 for _id in notify}
    else:
        activity['read'] = {}

    if item:
        activity['item'] = str(item)

    post_internal(ActivityModel.endpoint_name, activity)
    push_notification(ActivityModel.endpoint_name, _dest=activity['read'])
