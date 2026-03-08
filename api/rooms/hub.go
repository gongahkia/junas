package rooms

import "sync"

type Hub struct {
	mu          sync.RWMutex
	subscribers map[string]map[chan EventPayload]struct{}
}

func NewHub() *Hub {
	return &Hub{
		subscribers: make(map[string]map[chan EventPayload]struct{}),
	}
}

func (hub *Hub) Subscribe(roomSlug string) chan EventPayload {
	hub.mu.Lock()
	defer hub.mu.Unlock()

	ch := make(chan EventPayload, 8)
	if _, exists := hub.subscribers[roomSlug]; !exists {
		hub.subscribers[roomSlug] = make(map[chan EventPayload]struct{})
	}
	hub.subscribers[roomSlug][ch] = struct{}{}
	return ch
}

func (hub *Hub) Unsubscribe(roomSlug string, ch chan EventPayload) {
	hub.mu.Lock()
	defer hub.mu.Unlock()

	if subscribers, exists := hub.subscribers[roomSlug]; exists {
		delete(subscribers, ch)
		if len(subscribers) == 0 {
			delete(hub.subscribers, roomSlug)
		}
	}
	close(ch)
}

func (hub *Hub) Broadcast(event EventPayload) {
	hub.mu.RLock()
	defer hub.mu.RUnlock()

	for ch := range hub.subscribers[event.RoomSlug] {
		select {
		case ch <- event:
		default:
		}
	}
}
