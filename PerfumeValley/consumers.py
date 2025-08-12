# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from user_panel.models import Cart

class CartConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.cart_group_name = f'user_{self.user_id}_cart'

        # Join cart group
        await self.channel_layer.group_add(
            self.cart_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave cart group
        await self.channel_layer.group_discard(
            self.cart_group_name,
            self.channel_name
        )

    async def cart_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'action': event['action'],
            'item_id': event.get('item_id'),
            'item_key': event.get('item_key'),
            'quantity': event.get('quantity'),
            'cart_count': event['cart_count'],
            'is_empty': event['is_empty']
        }))

    @database_sync_to_async
    def get_cart_count(self, user_id):
        return Cart.objects.filter(user_id=user_id).count()