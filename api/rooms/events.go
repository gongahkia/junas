package rooms

type EventResource string

const (
	ResourceRoom         EventResource = "room"
	ResourceParticipants EventResource = "participants"
	ResourceQueue        EventResource = "queue"
	ResourceFinalists    EventResource = "finalists"
	ResourceVotes        EventResource = "votes"
	ResourceCatalog      EventResource = "catalog"
	ResourceConnection   EventResource = "connection"
	ResourceSurface      EventResource = "surface"
	ResourceCurrentClimb EventResource = "current_climb"
)

type EventBus interface {
	Subscribe(roomSlug string) chan EventPayload
	Unsubscribe(roomSlug string, ch chan EventPayload)
	Broadcast(event EventPayload)
	CloseAll()
	SubscriberCount() int
}

func NewEventPayload(eventType, roomSlug string, version int64, resources ...EventResource) EventPayload {
	return EventPayload{
		Type:      eventType,
		RoomSlug:  roomSlug,
		Version:   version,
		Resources: append([]EventResource(nil), resources...),
	}
}
