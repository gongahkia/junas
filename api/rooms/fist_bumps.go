package rooms

import (
	"sort"
	"sync"
)

type FistBumpStore struct {
	mu          sync.RWMutex
	bumpsByRoom map[uint]map[string]map[uint]struct{}
}

func NewFistBumpStore() *FistBumpStore {
	return &FistBumpStore{
		bumpsByRoom: make(map[uint]map[string]map[uint]struct{}),
	}
}

func (store *FistBumpStore) Toggle(roomID uint, participantID uint, climbID string) bool {
	store.mu.Lock()
	defer store.mu.Unlock()

	roomBumps := store.bumpsByRoom[roomID]
	if roomBumps == nil {
		roomBumps = make(map[string]map[uint]struct{})
		store.bumpsByRoom[roomID] = roomBumps
	}

	climbBumps := roomBumps[climbID]
	if climbBumps == nil {
		climbBumps = make(map[uint]struct{})
		roomBumps[climbID] = climbBumps
	}

	if _, exists := climbBumps[participantID]; exists {
		delete(climbBumps, participantID)
		if len(climbBumps) == 0 {
			delete(roomBumps, climbID)
		}
		if len(roomBumps) == 0 {
			delete(store.bumpsByRoom, roomID)
		}
		return false
	}

	climbBumps[participantID] = struct{}{}
	return true
}

func (store *FistBumpStore) VoteData(roomID uint, participantID uint) (map[string]int, []string) {
	store.mu.RLock()
	defer store.mu.RUnlock()

	voteCounts := make(map[string]int)
	myVotes := make([]string, 0)

	for climbID, climbBumps := range store.bumpsByRoom[roomID] {
		voteCounts[climbID] = len(climbBumps)
		if participantID != 0 {
			if _, exists := climbBumps[participantID]; exists {
				myVotes = append(myVotes, climbID)
			}
		}
	}

	sort.Strings(myVotes)
	return voteCounts, myVotes
}

func (store *FistBumpStore) Clear(roomID uint) {
	store.mu.Lock()
	defer store.mu.Unlock()

	delete(store.bumpsByRoom, roomID)
}

func (store *FistBumpStore) ClearParticipant(roomID uint, participantID uint) {
	store.mu.Lock()
	defer store.mu.Unlock()

	roomBumps := store.bumpsByRoom[roomID]
	if len(roomBumps) == 0 {
		return
	}

	for climbID, climbBumps := range roomBumps {
		delete(climbBumps, participantID)
		if len(climbBumps) == 0 {
			delete(roomBumps, climbID)
		}
	}

	if len(roomBumps) == 0 {
		delete(store.bumpsByRoom, roomID)
	}
}
