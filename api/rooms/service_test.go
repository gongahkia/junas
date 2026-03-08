package rooms

import (
	"bytes"
	"context"
	"encoding/base64"
	"path/filepath"
	"strings"
	"testing"

	"github.com/lczm/kilter-together/api/config"
	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/testutil/testprovider"
)

func TestServiceRoomLifecycle(t *testing.T) {
	ctx := context.Background()
	service, provider := setupRoomServiceTest(t)

	createdSnapshot, hostSessionID, err := service.CreateRoom(
		ctx,
		provider.ID(),
		"Session Alpha",
		"Host",
		providers.SecretPayload{"token": "provider-token"},
	)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}
	if createdSnapshot.ProviderID != provider.ID() {
		t.Fatalf("expected provider %q, got %q", provider.ID(), createdSnapshot.ProviderID)
	}
	if createdSnapshot.RoomName != "Session Alpha" {
		t.Fatalf("expected room name %q, got %#v", "Session Alpha", createdSnapshot.RoomName)
	}
	if !createdSnapshot.Connection.Connected {
		t.Fatalf("expected provider to be connected during room creation")
	}

	hostViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, hostSessionID, hostRole)
	if err != nil {
		t.Fatalf("authenticate host: %v", err)
	}

	renamedSnapshot, err := service.UpdateRoomName(ctx, hostViewer, "Session Beta")
	if err != nil {
		t.Fatalf("update room name: %v", err)
	}
	if renamedSnapshot.RoomName != "Session Beta" {
		t.Fatalf("expected updated room name %q, got %#v", "Session Beta", renamedSnapshot.RoomName)
	}

	connectionState, err := service.ConnectProvider(ctx, hostViewer, providers.SecretPayload{"token": "provider-token-2"})
	if err != nil {
		t.Fatalf("connect provider: %v", err)
	}
	if !connectionState.Connected {
		t.Fatalf("expected connected provider state")
	}

	var storedConnection RoomProviderConnection
	if err := config.AppDB.WithContext(ctx).Where("room_id = ?", hostViewer.Room.ID).First(&storedConnection).Error; err != nil {
		t.Fatalf("load stored provider connection: %v", err)
	}
	if strings.Contains(storedConnection.SecretCiphertext, "provider-token") {
		t.Fatalf("expected encrypted provider secret at rest")
	}

	surfaces, err := service.ListSurfaces(ctx, hostViewer, providers.SurfaceFilter{})
	if err != nil {
		t.Fatalf("list surfaces: %v", err)
	}
	if len(surfaces) != 2 {
		t.Fatalf("expected two test surfaces, got %d", len(surfaces))
	}

	surface, err := service.SetSurface(ctx, hostViewer, "wall-alpha", map[string]string{})
	if err != nil {
		t.Fatalf("set surface: %v", err)
	}
	if surface.Name != "Alpha Wall" {
		t.Fatalf("expected selected surface Alpha Wall, got %#v", surface)
	}

	guestSnapshot, guestSessionID, err := service.JoinRoom(ctx, createdSnapshot.Slug, "Guest")
	if err != nil {
		t.Fatalf("join room: %v", err)
	}
	if len(guestSnapshot.Participants) != 2 {
		t.Fatalf("expected host and guest participants, got %#v", guestSnapshot.Participants)
	}
	if guestSnapshot.Participants[0].Status != participantStatusWatching || guestSnapshot.Participants[1].Status != participantStatusWatching {
		t.Fatalf("expected watching to be the default participant status, got %#v", guestSnapshot.Participants)
	}

	guestViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, guestSessionID, "")
	if err != nil {
		t.Fatalf("authenticate guest: %v", err)
	}

	climbsResponse, err := service.ListCatalogClimbs(ctx, guestViewer, "beta", "popular", "", 10)
	if err != nil {
		t.Fatalf("list catalog climbs: %v", err)
	}
	if len(climbsResponse.Climbs) != 1 || climbsResponse.Climbs[0].ID != "fake-room:beta" {
		t.Fatalf("unexpected filtered climbs response: %#v", climbsResponse.Climbs)
	}

	climbResponse, err := service.GetCatalogClimb(ctx, guestViewer, "fake-room:beta")
	if err != nil {
		t.Fatalf("get catalog climb: %v", err)
	}
	if climbResponse.Climb.Name != "Beta Crimp" {
		t.Fatalf("expected Beta Crimp climb, got %#v", climbResponse.Climb)
	}

	if err := service.ToggleVote(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add guest vote: %v", err)
	}
	if err := service.ToggleVote(ctx, hostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add host vote: %v", err)
	}
	if err := service.AddQueueEntry(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("queue climb: %v", err)
	}
	if err := service.AddQueueEntry(ctx, hostViewer, "fake-room:alpha"); err != nil {
		t.Fatalf("queue second climb: %v", err)
	}
	if err := service.AddFinalist(ctx, hostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add finalist: %v", err)
	}
	if err := service.AddFinalist(ctx, hostViewer, "fake-room:alpha"); err != nil {
		t.Fatalf("add second finalist: %v", err)
	}
	if err := service.UpdateParticipantStatus(ctx, guestViewer, participantStatusReady); err != nil {
		t.Fatalf("update participant status: %v", err)
	}

	snapshotAfterVotes, err := service.GetSnapshot(ctx, guestViewer)
	if err != nil {
		t.Fatalf("get snapshot after votes: %v", err)
	}
	if snapshotAfterVotes.VoteCounts["fake-room:beta"] != 2 {
		t.Fatalf("expected two votes for fake-room:beta, got %#v", snapshotAfterVotes.VoteCounts)
	}
	if len(snapshotAfterVotes.Queue) != 2 {
		t.Fatalf("expected two queued climbs, got %#v", snapshotAfterVotes.Queue)
	}
	if len(snapshotAfterVotes.Finalists) != 2 {
		t.Fatalf("expected two finalists, got %#v", snapshotAfterVotes.Finalists)
	}
	if snapshotAfterVotes.Participants[1].Status != participantStatusReady {
		t.Fatalf("expected guest status to update, got %#v", snapshotAfterVotes.Participants)
	}

	entryIDs := []uint{snapshotAfterVotes.Queue[1].ID, snapshotAfterVotes.Queue[0].ID}
	if err := service.ReorderQueue(ctx, hostViewer, entryIDs); err != nil {
		t.Fatalf("reorder queue: %v", err)
	}
	finalistIDs := []uint{snapshotAfterVotes.Finalists[1].ID, snapshotAfterVotes.Finalists[0].ID}
	if err := service.ReorderFinalists(ctx, hostViewer, finalistIDs); err != nil {
		t.Fatalf("reorder finalists: %v", err)
	}
	if err := service.UpdateQueueEntryStatus(ctx, hostViewer, entryIDs[0], queueStatusCurrent); err != nil {
		t.Fatalf("set current queue entry: %v", err)
	}
	if err := service.PromoteClimb(ctx, hostViewer, "fake-room:beta", queueStatusNext); err != nil {
		t.Fatalf("promote climb to next: %v", err)
	}

	currentSnapshot, err := service.GetSnapshot(ctx, hostViewer)
	if err != nil {
		t.Fatalf("get current snapshot: %v", err)
	}
	if currentSnapshot.CurrentClimb == nil || currentSnapshot.CurrentClimb.ID != "fake-room:alpha" {
		t.Fatalf("expected fake-room:alpha to be current climb, got %#v", currentSnapshot.CurrentClimb)
	}
	if currentSnapshot.Queue[0].Status != queueStatusCurrent || currentSnapshot.Queue[1].Status != queueStatusNext {
		t.Fatalf("expected queue promotion states, got %#v", currentSnapshot.Queue)
	}
	if currentSnapshot.Finalists[0].Climb.ID != "fake-room:alpha" {
		t.Fatalf("expected finalist reorder to put fake-room:alpha first, got %#v", currentSnapshot.Finalists)
	}

	randomFinalist, err := service.PickRandom(ctx, hostViewer, "finalists")
	if err != nil {
		t.Fatalf("pick random finalist: %v", err)
	}
	if randomFinalist.ID != "fake-room:alpha" && randomFinalist.ID != "fake-room:beta" {
		t.Fatalf("unexpected random finalist climb: %#v", randomFinalist)
	}

	randomTopVoted, err := service.PickRandom(ctx, hostViewer, "top_voted")
	if err != nil {
		t.Fatalf("pick random top voted climb: %v", err)
	}
	if randomTopVoted.ID != "fake-room:beta" {
		t.Fatalf("expected fake-room:beta top-voted climb, got %#v", randomTopVoted)
	}

	if err := service.DeleteFinalist(ctx, hostViewer, currentSnapshot.Finalists[1].ID); err != nil {
		t.Fatalf("delete finalist: %v", err)
	}

	if err := service.ClearVotes(ctx, hostViewer); err != nil {
		t.Fatalf("clear votes: %v", err)
	}
	if err := service.RemoveParticipant(ctx, hostViewer, guestViewer.Participant.ID); err != nil {
		t.Fatalf("remove participant: %v", err)
	}
	if err := service.CloseRoom(ctx, hostViewer); err != nil {
		t.Fatalf("close room: %v", err)
	}

	finalSnapshot, err := service.GetSnapshot(ctx, hostViewer)
	if err != nil {
		t.Fatalf("get final snapshot: %v", err)
	}
	if finalSnapshot.Status != roomStatusClosed {
		t.Fatalf("expected closed room, got %#v", finalSnapshot)
	}
	if len(finalSnapshot.Participants) != 1 {
		t.Fatalf("expected guest removal in final snapshot, got %#v", finalSnapshot.Participants)
	}
	if len(finalSnapshot.VoteCounts) != 0 {
		t.Fatalf("expected votes cleared, got %#v", finalSnapshot.VoteCounts)
	}
	if len(finalSnapshot.Finalists) != 1 {
		t.Fatalf("expected finalist deletion to persist, got %#v", finalSnapshot.Finalists)
	}
}

func setupRoomServiceTest(t *testing.T) (*Service, *testprovider.Provider) {
	t.Helper()

	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	encryptionKey := base64.StdEncoding.EncodeToString(bytes.Repeat([]byte{3}, 32))
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:       tempDir,
		AppDBPath:     appDBPath,
		AppSecret:     "test-app-secret",
		EncryptionKey: encryptionKey,
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app database: %v", err)
	}

	provider := testprovider.New(providers.ProviderID("fake-room"))
	providers.Register(provider)

	service := NewService()
	if err := service.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	return service, provider
}
