package rooms

import (
	"crypto/rand"
	"encoding/hex"
	"sync"
	"time"
)

const (
	sseTicketTTL       = 30 * time.Second
	sseTicketPurgeFreq = 60 * time.Second
)

type sseTicketEntry struct {
	SessionID string
	RoomSlug  string
	ExpiresAt time.Time
}

type SSETicketStore struct {
	mu      sync.Mutex
	tickets map[string]sseTicketEntry
	done    chan struct{}
}

func NewSSETicketStore() *SSETicketStore {
	s := &SSETicketStore{
		tickets: make(map[string]sseTicketEntry),
		done:    make(chan struct{}),
	}
	go s.purgeLoop()
	return s
}

func (s *SSETicketStore) Issue(roomSlug, sessionID string) (string, time.Time) {
	buf := make([]byte, 24)
	if _, err := rand.Read(buf); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	ticket := hex.EncodeToString(buf)
	expiresAt := time.Now().UTC().Add(sseTicketTTL)
	s.mu.Lock()
	s.tickets[ticket] = sseTicketEntry{
		SessionID: sessionID,
		RoomSlug:  roomSlug,
		ExpiresAt: expiresAt,
	}
	s.mu.Unlock()
	return ticket, expiresAt
}

// Consume validates and removes a ticket (single-use). Returns the session ID or empty string.
func (s *SSETicketStore) Consume(ticket, roomSlug string) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	entry, ok := s.tickets[ticket]
	if !ok {
		return ""
	}
	delete(s.tickets, ticket)
	if entry.RoomSlug != roomSlug || entry.ExpiresAt.Before(time.Now().UTC()) {
		return ""
	}
	return entry.SessionID
}

func (s *SSETicketStore) Close() {
	close(s.done)
}

func (s *SSETicketStore) purgeLoop() {
	ticker := time.NewTicker(sseTicketPurgeFreq)
	defer ticker.Stop()
	for {
		select {
		case <-s.done:
			return
		case now := <-ticker.C:
			s.mu.Lock()
			for id, entry := range s.tickets {
				if entry.ExpiresAt.Before(now) {
					delete(s.tickets, id)
				}
			}
			s.mu.Unlock()
		}
	}
}
