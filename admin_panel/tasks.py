from celery import shared_task
import requests
from admin_panel.models import Order, Notification
from admin_panel.utils import get_shiprocket_token, send_push_notification
from django.utils import timezone
from datetime import datetime


@shared_task
# Setup Django environment


def fetch_tracking_status():
    orders = Order.objects.exclude(shiprocket_awb_code__isnull=True).exclude(shiprocket_awb_code='')

    for order in orders:
        try:
            token = get_shiprocket_token()
            url = f"https://apiv2.shiprocket.in/v1/external/courier/track/awb/{order.shiprocket_awb_code}"
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                tracking_data = data.get("tracking_data", {})
                shipment_tracks = tracking_data.get("shipment_track", [])

                # Normalize if it's a single object
                if isinstance(shipment_tracks, dict):
                    shipment_tracks = [shipment_tracks]
                elif not isinstance(shipment_tracks, list):
                    shipment_tracks = []

                if not shipment_tracks:
                    print(f"⚠️ No shipment_track data for Order #{order.id}")
                    continue

                latest_track = shipment_tracks[-1]
                current_status = latest_track.get("current_status", "")
                etd = tracking_data.get("etd", "")
                updated_at = datetime.now()

                # Always print full timeline
                print(f"\n📦 Shipment Timeline for Order #{order.id}:")
                for i, track in enumerate(shipment_tracks, start=1):
                    print(f" Step {i}:")
                    print(f"   Status      : {track.get('current_status')}")
                    print(f"   Origin      : {track.get('origin')}")
                    print(f"   Destination : {track.get('destination')}")
                    print(f"   Updated At  : {track.get('updated_time_stamp')}")
                    print(f"   Courier     : {track.get('courier_name')}")
                    print()

                # Update DB only if the status changed
                if current_status and current_status != order.shiprocket_tracking_status:
                    order.shiprocket_tracking_status = current_status
                    order.shiprocket_tracking_info = tracking_data
                    order.shiprocket_estimated_delivery = etd
                    order.shiprocket_tracking_events = shipment_tracks
                    order.shiprocket_tracking_status_updated_at = timezone.now()  # ✅ Update timestamp

                    order.save(update_fields=[
                        'shiprocket_tracking_status',
                        'shiprocket_tracking_info',
                        'shiprocket_estimated_delivery',
                        'shiprocket_tracking_events',
                        'shiprocket_tracking_status_updated_at'
                    ])
                    print(f"✅ Updated Order #{order.id}: {current_status} at {updated_at}")
                else:
                    print(f"ℹ️ Order #{order.id} already up to date: {current_status}")

            elif response.status_code == 500:
                error_msg = response.json().get("message", "Unknown error")
                print(f"❌ Order #{order.id} - AWB may be cancelled: {error_msg}")
            else:
                print(f"❌ Order #{order.id} error: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"⚠️ Error tracking Order #{order.id}: {e}")

# 🔁 Run the updater for all AWB-assigned orders

