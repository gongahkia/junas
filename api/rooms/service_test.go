package rooms

import (
	"bytes"
	"context"
	"encoding/base64"
	"errors"
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
		true,
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
	if !createdSnapshot.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to default on")
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

	climbsResponse, err := service.ListCatalogClimbs(ctx, guestViewer, "beta", "popular", "", 10, "", "")
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

	if err := service.ToggleVote(ctx, guestViewer, "fake-room:beta"); !errors.Is(err, ErrClimbNotQueued) {
		t.Fatalf("expected unqueued climb fist bump to fail, got %v", err)
	}
	if err := service.AddQueueEntry(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("queue climb: %v", err)
	}
	if err := service.AddQueueEntry(ctx, hostViewer, "fake-room:alpha"); err != nil {
		t.Fatalf("queue second climb: %v", err)
	}
	if err := service.ToggleVote(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add guest vote: %v", err)
	}
	if err := service.ToggleVote(ctx, hostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add host vote: %v", err)
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

	fistBumpsDisabledSnapshot, err := service.SetFistBumpsEnabled(ctx, hostViewer, false)
	if err != nil {
		t.Fatalf("disable fist bumps: %v", err)
	}
	if fistBumpsDisabledSnapshot.FistBumpsEnabled {
		t.Fatalf("expected fist bumps to be disabled")
	}
	if err := service.ToggleVote(ctx, guestViewer, "fake-room:alpha"); !errors.Is(err, ErrFistBumpsOff) {
		t.Fatalf("expected disabled fist bumps error, got %v", err)
	}
	if _, err := service.SetFistBumpsEnabled(ctx, hostViewer, true); err != nil {
		t.Fatalf("re-enable fist bumps: %v", err)
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

	originalClimbs := append([]providers.ProviderClimb{}, provider.Climbs...)
	provider.Climbs = nil
	cachedSnapshot, err := service.GetSnapshot(ctx, hostViewer)
	if err != nil {
		t.Fatalf("get cached snapshot: %v", err)
	}
	if cachedSnapshot.CurrentClimb == nil || cachedSnapshot.CurrentClimb.ID != "fake-room:alpha" {
		t.Fatalf("expected cached current climb, got %#v", cachedSnapshot.CurrentClimb)
	}
	if len(cachedSnapshot.Queue) != 2 || cachedSnapshot.Queue[0].Climb.ID != "fake-room:alpha" || cachedSnapshot.Queue[1].Climb.ID != "fake-room:beta" {
		t.Fatalf("expected cached queue climbs, got %#v", cachedSnapshot.Queue)
	}
	if len(cachedSnapshot.Finalists) != 2 || cachedSnapshot.Finalists[0].Climb.ID != "fake-room:alpha" || cachedSnapshot.Finalists[1].Climb.ID != "fake-room:beta" {
		t.Fatalf("expected cached finalist climbs, got %#v", cachedSnapshot.Finalists)
	}
	provider.Climbs = originalClimbs

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

func TestServiceFistBumpsAreEphemeral(t *testing.T) {
	ctx := context.Background()
	service, provider := setupRoomServiceTest(t)

	createdSnapshot, _, err := service.CreateRoom(
		ctx,
		provider.ID(),
		"Ephemeral Session",
		"Host",
		providers.SecretPayload{"token": "provider-token"},
		true,
	)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	guestSnapshot, guestSessionID, err := service.JoinRoom(ctx, createdSnapshot.Slug, "Guest")
	if err != nil {
		t.Fatalf("join room: %v", err)
	}
	guestViewer, err := service.Authenticate(ctx, guestSnapshot.Slug, guestSessionID, "")
	if err != nil {
		t.Fatalf("authenticate guest: %v", err)
	}
	if err := service.AddQueueEntry(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("queue climb: %v", err)
	}
	if err := service.ToggleVote(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("toggle fist bump: %v", err)
	}

	snapshotBeforeRestart, err := service.GetSnapshot(ctx, guestViewer)
	if err != nil {
		t.Fatalf("get snapshot before restart: %v", err)
	}
	if snapshotBeforeRestart.VoteCounts["fake-room:beta"] != 1 {
		t.Fatalf("expected one fist bump before restart, got %#v", snapshotBeforeRestart.VoteCounts)
	}

	restartedService := NewService()
	if err := restartedService.Migrate(ctx); err != nil {
		t.Fatalf("migrate restarted service: %v", err)
	}
	restartedGuestViewer, err := restartedService.Authenticate(ctx, guestSnapshot.Slug, guestSessionID, "")
	if err != nil {
		t.Fatalf("authenticate guest after restart: %v", err)
	}

	snapshotAfterRestart, err := restartedService.GetSnapshot(ctx, restartedGuestViewer)
	if err != nil {
		t.Fatalf("get snapshot after restart: %v", err)
	}
	if len(snapshotAfterRestart.VoteCounts) != 0 {
		t.Fatalf("expected fist bumps to be ephemeral across restarts, got %#v", snapshotAfterRestart.VoteCounts)
	}
	if len(snapshotAfterRestart.MyVotes) != 0 {
		t.Fatalf("expected participant fist bump state to reset across restarts, got %#v", snapshotAfterRestart.MyVotes)
	}
}

func TestServiceCoHostPermissions(t *testing.T) {
	ctx := context.Background()
	service, provider := setupRoomServiceTest(t)

	createdSnapshot, hostSessionID, err := service.CreateRoom(
		ctx,
		provider.ID(),
		"Co-Host Session",
		"Host",
		providers.SecretPayload{"token": "provider-token"},
		true,
	)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	hostViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, hostSessionID, "")
	if err != nil {
		t.Fatalf("authenticate host: %v", err)
	}

	guestSnapshot, guestSessionID, err := service.JoinRoom(ctx, createdSnapshot.Slug, "CoHost")
	if err != nil {
		t.Fatalf("join room: %v", err)
	}
	var coHostParticipantID uint
	for _, participant := range guestSnapshot.Participants {
		if participant.DisplayName == "CoHost" {
			coHostParticipantID = participant.ID
			break
		}
	}
	if coHostParticipantID == 0 {
		t.Fatalf("expected to find co-host participant id")
	}

	if err := service.UpdateParticipantRole(ctx, hostViewer, coHostParticipantID, coHostRole); err != nil {
		t.Fatalf("promote to co-host: %v", err)
	}

	coHostViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, guestSessionID, "")
	if err != nil {
		t.Fatalf("authenticate co-host: %v", err)
	}
	if !coHostViewer.IsCoHost() {
		t.Fatalf("expected co-host role, got %q", coHostViewer.Session.Role)
	}

	if _, err := service.SetSurface(ctx, coHostViewer, "wall-alpha", map[string]string{}); err != nil {
		t.Fatalf("co-host set surface: %v", err)
	}
	if err := service.AddQueueEntry(ctx, coHostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("co-host queue climb: %v", err)
	}
	if err := service.AddFinalist(ctx, coHostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("co-host add finalist: %v", err)
	}

	snapshot, err := service.GetSnapshot(ctx, coHostViewer)
	if err != nil {
		t.Fatalf("get co-host snapshot: %v", err)
	}
	if !snapshot.CanManage || !snapshot.Permissions.ManageQueue || !snapshot.Permissions.ManageSurface {
		t.Fatalf("expected co-host management permissions, got %#v", snapshot.Permissions)
	}
	if snapshot.Permissions.EditRoomSettings || snapshot.Permissions.AssignCoHosts || snapshot.Permissions.CloseRoom {
		t.Fatalf("expected host-only permissions to remain false, got %#v", snapshot.Permissions)
	}

	if _, err := service.UpdateRoomName(ctx, coHostViewer, "Blocked"); !errors.Is(err, ErrForbidden) {
		t.Fatalf("expected room rename to stay host-only, got %v", err)
	}
	if err := service.RemoveParticipant(ctx, coHostViewer, hostViewer.Participant.ID); !errors.Is(err, ErrForbidden) {
		t.Fatalf("expected participant removal to stay host-only, got %v", err)
	}
}

func TestServicePersistsRoomSessionSummaryOnClose(t *testing.T) {
	ctx := context.Background()
	service, provider := setupRoomServiceTest(t)

	createdSnapshot, hostSessionID, err := service.CreateRoom(
		ctx,
		provider.ID(),
		"Summary Session",
		"Host",
		providers.SecretPayload{"token": "provider-token"},
		true,
	)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	hostViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, hostSessionID, "")
	if err != nil {
		t.Fatalf("authenticate host: %v", err)
	}
	if _, err := service.SetSurface(ctx, hostViewer, "wall-alpha", map[string]string{}); err != nil {
		t.Fatalf("set surface: %v", err)
	}

	_, guestSessionID, err := service.JoinRoom(ctx, createdSnapshot.Slug, "Guest")
	if err != nil {
		t.Fatalf("join room: %v", err)
	}
	guestViewer, err := service.Authenticate(ctx, createdSnapshot.Slug, guestSessionID, "")
	if err != nil {
		t.Fatalf("authenticate guest: %v", err)
	}

	if err := service.AddQueueEntry(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("queue beta: %v", err)
	}
	if err := service.AddQueueEntry(ctx, hostViewer, "fake-room:alpha"); err != nil {
		t.Fatalf("queue alpha: %v", err)
	}
	if err := service.ToggleVote(ctx, guestViewer, "fake-room:beta"); err != nil {
		t.Fatalf("guest vote beta: %v", err)
	}
	if err := service.ToggleVote(ctx, hostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("host vote beta: %v", err)
	}
	if err := service.AddFinalist(ctx, hostViewer, "fake-room:beta"); err != nil {
		t.Fatalf("add finalist: %v", err)
	}
	if err := service.CloseRoom(ctx, hostViewer); err != nil {
		t.Fatalf("close room: %v", err)
	}

	summaries, err := service.ListRecentSessionSummaries(ctx, 5)
	if err != nil {
		t.Fatalf("list recent sessions: %v", err)
	}
	if len(summaries) != 1 {
		t.Fatalf("expected one summary, got %#v", summaries)
	}

	summary := summaries[0]
	if summary.RoomSlug != createdSnapshot.Slug || summary.RoomName != "Summary Session" {
		t.Fatalf("unexpected summary identity: %#v", summary)
	}
	if summary.ProviderID != provider.ID() {
		t.Fatalf("unexpected summary provider: %#v", summary.ProviderID)
	}
	if summary.SurfaceName != "Alpha Wall" {
		t.Fatalf("expected surface name to persist, got %#v", summary.SurfaceName)
	}
	if summary.ParticipantCount != 2 {
		t.Fatalf("expected two participants in summary, got %#v", summary.ParticipantCount)
	}
	if len(summary.FinalQueue) != 2 {
		t.Fatalf("expected two queue entries in summary, got %#v", summary.FinalQueue)
	}
	if len(summary.Finalists) != 1 || summary.Finalists[0].Climb.ID != "fake-room:beta" {
		t.Fatalf("unexpected finalists summary: %#v", summary.Finalists)
	}
	if len(summary.TopVoted) != 1 || summary.TopVoted[0].Climb.ID != "fake-room:beta" || summary.TopVoted[0].VoteCount != 2 {
		t.Fatalf("unexpected top-voted summary: %#v", summary.TopVoted)
	}
}

func TestServiceCreateKilterRoomWithoutSecretOrEncryptionKey(t *testing.T) {
	tempDir := t.TempDir()
	appDBPath := filepath.Join(tempDir, "app.db")
	config.SetRuntimeConfig(config.RuntimeConfig{
		DataDir:   tempDir,
		AppDBPath: appDBPath,
		AppSecret: "test-app-secret",
	})
	if err := config.ConnectAppDB(appDBPath); err != nil {
		t.Fatalf("connect app database: %v", err)
	}

	service := NewService()
	if err := service.Migrate(context.Background()); err != nil {
		t.Fatalf("migrate app database: %v", err)
	}

	createdSnapshot, hostSessionID, err := service.CreateRoom(
		context.Background(),
		providers.ProviderKilter,
		"Local Kilter",
		"Host",
		providers.SecretPayload{},
		true,
	)
	if err != nil {
		t.Fatalf("create kilter room: %v", err)
	}
	if !createdSnapshot.Connection.Connected {
		t.Fatalf("expected Kilter room connection to be ready without secrets")
	}

	hostViewer, err := service.Authenticate(context.Background(), createdSnapshot.Slug, hostSessionID, hostRole)
	if err != nil {
		t.Fatalf("authenticate host: %v", err)
	}

	snapshot, err := service.GetSnapshot(context.Background(), hostViewer)
	if err != nil {
		t.Fatalf("get snapshot: %v", err)
	}
	if !snapshot.Connection.Connected {
		t.Fatalf("expected Kilter room snapshot to remain connected without stored secrets")
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
