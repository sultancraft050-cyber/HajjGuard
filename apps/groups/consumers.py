import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import GroupMembership


class GroupConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        if not self.scope['user'].is_authenticated or not await self.is_member():
            await self.close(code=4403)
            return
        self.channel_group = f'group-{self.group_id}'
        await self.channel_layer.group_add(self.channel_group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'channel_group'):
            await self.channel_layer.group_discard(self.channel_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Client messages are handled by authenticated HTTP endpoints in Phase A.
        await self.send_json({'type': 'error', 'message': 'Use the authenticated group API for writes.'})

    async def group_event(self, event):
        if not await self.is_member():
            await self.close(code=4403)
            return
        await self.send_json(event['payload'])

    @database_sync_to_async
    def is_member(self):
        return GroupMembership.objects.filter(
            group_id=self.group_id, pilgrim__user=self.scope['user'], is_active=True
        ).exists()
