package rooms

import "testing"

func TestHubCloseAllClosesSubscribersAndKeepsUnsubscribeSafe(t *testing.T) {
	hub := NewHub()

	roomOneChannel := hub.Subscribe("room-one")
	roomTwoChannel := hub.Subscribe("room-two")

	hub.CloseAll()

	if _, ok := <-roomOneChannel; ok {
		t.Fatal("expected room-one channel to be closed")
	}
	if _, ok := <-roomTwoChannel; ok {
		t.Fatal("expected room-two channel to be closed")
	}

	hub.Unsubscribe("room-one", roomOneChannel)
	hub.Unsubscribe("room-two", roomTwoChannel)

	replacementChannel := hub.Subscribe("room-one")
	hub.Broadcast(EventPayload{Type: "room.updated", RoomSlug: "room-one", Version: 2})

	select {
	case event := <-replacementChannel:
		if event.RoomSlug != "room-one" {
			t.Fatalf("expected replacement channel to receive room-one event, got %#v", event)
		}
	default:
		t.Fatal("expected replacement channel to receive broadcast")
	}

	hub.Unsubscribe("room-one", replacementChannel)
}
