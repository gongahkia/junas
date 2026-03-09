package rooms

import (
	"fmt"
	"strings"
	"sync"
	"time"
)

const (
	reactionCodeThumbsUp  = "thumbs_up"
	reactionCodeHeart     = "heart"
	reactionCodeClap      = "clap"
	reactionCodeFire      = "fire"
	reactionCodeMindBlown = "mind_blown"
	reactionCodeParty     = "party"

	roomReactionLifetime = 12 * time.Second
	maxRoomReactions     = 24
)

type ReactionStore struct {
	mu              sync.Mutex
	reactionsByRoom map[uint][]RoomReactionView
}

func NewReactionStore() *ReactionStore {
	return &ReactionStore{
		reactionsByRoom: make(map[uint][]RoomReactionView),
	}
}

func normalizeReactionCode(value string) string {
	return strings.ToLower(strings.TrimSpace(value))
}

func isValidReactionCode(value string) bool {
	switch normalizeReactionCode(value) {
	case reactionCodeThumbsUp, reactionCodeHeart, reactionCodeClap, reactionCodeFire, reactionCodeMindBlown, reactionCodeParty:
		return true
	default:
		return false
	}
}

func (store *ReactionStore) Add(
	roomID uint,
	participant RoomParticipant,
	emojiCode string,
	now time.Time,
) RoomReactionView {
	store.mu.Lock()
	defer store.mu.Unlock()

	store.trimLocked(roomID, now)

	reaction := RoomReactionView{
		ID:          fmt.Sprintf("%d-%d-%s-%d", roomID, participant.ID, emojiCode, now.UnixNano()),
		EmojiCode:   emojiCode,
		DisplayName: participant.DisplayName,
		Role:        participant.Role,
		CreatedAt:   now,
	}

	reactions := append(store.reactionsByRoom[roomID], reaction)
	if len(reactions) > maxRoomReactions {
		reactions = reactions[len(reactions)-maxRoomReactions:]
	}
	store.reactionsByRoom[roomID] = reactions
	return reaction
}

func (store *ReactionStore) List(roomID uint, now time.Time) []RoomReactionView {
	store.mu.Lock()
	defer store.mu.Unlock()

	store.trimLocked(roomID, now)
	reactions := store.reactionsByRoom[roomID]
	if len(reactions) == 0 {
		return []RoomReactionView{}
	}

	copied := make([]RoomReactionView, len(reactions))
	copy(copied, reactions)
	return copied
}

func (store *ReactionStore) Clear(roomID uint) {
	store.mu.Lock()
	defer store.mu.Unlock()

	delete(store.reactionsByRoom, roomID)
}

func (store *ReactionStore) trimLocked(roomID uint, now time.Time) {
	reactions := store.reactionsByRoom[roomID]
	if len(reactions) == 0 {
		return
	}

	cutoff := now.Add(-roomReactionLifetime)
	trimIndex := 0
	for trimIndex < len(reactions) && reactions[trimIndex].CreatedAt.Before(cutoff) {
		trimIndex++
	}

	switch {
	case trimIndex >= len(reactions):
		delete(store.reactionsByRoom, roomID)
	case trimIndex > 0:
		store.reactionsByRoom[roomID] = append([]RoomReactionView(nil), reactions[trimIndex:]...)
	}
}
