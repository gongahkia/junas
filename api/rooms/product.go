package rooms

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/lczm/kilter-together/api/providers"
	"github.com/lczm/kilter-together/api/security"
	"gorm.io/gorm"
)

const (
	assistantModeManual   = "manual"
	assistantModeAssist   = "assist"
	analyticsRetentionTTL = 180 * 24 * time.Hour
)

type AnalyticsEventInput struct {
	RoomSlug   string
	EventName  string
	Source     string
	ViewerRole string
	Route      string
	Properties map[string]any
}

type FeedbackInput struct {
	RoomSlug     string
	ShareID      string
	PromptFamily string
	Sentiment    string
	Message      string
	Route        string
	Metadata     map[string]any
}

type RecapStatView struct {
	Label string `json:"label"`
	Value string `json:"value"`
}

type RecapSlideView struct {
	ID            string                    `json:"id"`
	Eyebrow       string                    `json:"eyebrow"`
	Title         string                    `json:"title"`
	Description   string                    `json:"description"`
	Stats         []RecapStatView           `json:"stats,omitempty"`
	FeaturedClimb *providers.ProviderClimb  `json:"featured_climb,omitempty"`
	Climbs        []SessionSummaryClimbView `json:"climbs,omitempty"`
	Participants  []string                  `json:"participants,omitempty"`
}

type RoomSeedView struct {
	ProviderID providers.ProviderID      `json:"provider_id"`
	Surface    providers.ProviderSurface `json:"surface"`
	Climbs     []providers.ProviderClimb `json:"climbs"`
}

type RoomRecapView struct {
	ShareID     string               `json:"share_id"`
	RoomSlug    string               `json:"room_slug"`
	RoomName    string               `json:"room_name,omitempty"`
	ProviderID  providers.ProviderID `json:"provider_id"`
	SurfaceName string               `json:"surface_name,omitempty"`
	ClosedAt    time.Time            `json:"closed_at"`
	Slides      []RecapSlideView     `json:"slides"`
	RematchSeed *RoomSeedView        `json:"rematch_seed,omitempty"`
}

type SoloPlanCreateInput struct {
	ProviderID providers.ProviderID
	Title      string
	Notes      string
	Surface    providers.ProviderSurface
	Context    map[string]string
	Filters    map[string]string
	Climbs     []providers.ProviderClimb
	OpenPath   string
	CreatedBy  string
}

type SoloPlanSnapshotView struct {
	ShareID    string                    `json:"share_id"`
	ProviderID providers.ProviderID      `json:"provider_id"`
	Title      string                    `json:"title"`
	Notes      string                    `json:"notes,omitempty"`
	Surface    providers.ProviderSurface `json:"surface"`
	Filters    map[string]string         `json:"filters,omitempty"`
	Climbs     []providers.ProviderClimb `json:"climbs"`
	OpenPath   string                    `json:"open_path,omitempty"`
	CreatedBy  string                    `json:"created_by,omitempty"`
	CreatedAt  time.Time                 `json:"created_at"`
}

type ProductBreakdownView struct {
	Key   string `json:"key"`
	Count int64  `json:"count"`
}

type ProductMetricsView struct {
	Status            string                 `json:"status"`
	GeneratedAt       time.Time              `json:"generated_at"`
	RetentionDays     int                    `json:"retention_days"`
	TotalEvents       int64                  `json:"total_events"`
	TotalRecaps       int64                  `json:"total_recaps"`
	TotalPlans        int64                  `json:"total_plans"`
	TotalFeedback     int64                  `json:"total_feedback"`
	EventsLast7Days   []ProductBreakdownView `json:"events_last_7_days"`
	FeedbackSentiment []ProductBreakdownView `json:"feedback_sentiment"`
	FeedbackByPrompt  []ProductBreakdownView `json:"feedback_by_prompt"`
}

type groupedCountRow struct {
	Key   string
	Count int64
}

func normalizeAssistantMode(mode string) string {
	switch strings.ToLower(strings.TrimSpace(mode)) {
	case assistantModeAssist:
		return assistantModeAssist
	default:
		return assistantModeManual
	}
}

func (service *Service) UpdateAssistantMode(
	ctx context.Context,
	viewer *Viewer,
	mode string,
) (*RoomSnapshot, error) {
	if !viewer.CanManageSession() {
		return nil, ErrForbidden
	}

	normalizedMode := normalizeAssistantMode(mode)
	err := service.store.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		if err := tx.Model(&Room{}).
			Where("id = ?", viewer.Room.ID).
			Update("assistant_mode", normalizedMode).Error; err != nil {
			return err
		}
		return service.bumpRoomVersion(tx, &viewer.Room)
	})
	if err != nil {
		return nil, err
	}

	viewer.Room.AssistantMode = normalizedMode
	service.broadcastRoomEvent(&viewer.Room, viewer.Participant.ID, "assistant.updated", ResourceRoom)
	_ = service.RecordAnalyticsEvent(ctx, AnalyticsEventInput{
		RoomSlug:   viewer.Room.Slug,
		EventName:  "room.assistant.updated",
		Source:     "server",
		ViewerRole: viewer.Session.Role,
		Properties: map[string]any{"mode": normalizedMode},
	})

	return service.buildSnapshot(ctx, viewer.Room.Slug, viewer)
}

func (service *Service) RecordAnalyticsEvent(ctx context.Context, input AnalyticsEventInput) error {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return err
	}
	return service.recordAnalyticsEventTx(db, input)
}

func (service *Service) recordAnalyticsEventTx(tx *gorm.DB, input AnalyticsEventInput) error {
	if tx == nil {
		return fmt.Errorf("app database is not configured")
	}

	eventName := strings.TrimSpace(input.EventName)
	if eventName == "" {
		return fmt.Errorf("event name is required")
	}

	source := strings.TrimSpace(input.Source)
	if source == "" {
		source = "client"
	}

	var roomID *uint
	roomSlug := strings.TrimSpace(input.RoomSlug)
	if roomSlug != "" {
		var room Room
		if err := tx.Where("slug = ?", roomSlug).First(&room).Error; err == nil {
			roomID = &room.ID
			roomSlug = room.Slug
		}
	}

	event := AnalyticsEvent{
		RoomID:         roomID,
		RoomSlug:       roomSlug,
		EventName:      eventName,
		Source:         source,
		ViewerRole:     strings.TrimSpace(input.ViewerRole),
		Route:          strings.TrimSpace(input.Route),
		PropertiesJSON: mustEncodeAnyJSON(input.Properties),
		CreatedAt:      time.Now().UTC(),
	}
	return tx.Create(&event).Error
}

func (service *Service) SubmitFeedback(ctx context.Context, input FeedbackInput) error {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return err
	}

	promptFamily := strings.TrimSpace(input.PromptFamily)
	sentiment := strings.ToLower(strings.TrimSpace(input.Sentiment))
	if promptFamily == "" {
		return fmt.Errorf("prompt family is required")
	}
	if sentiment != "up" && sentiment != "down" {
		return fmt.Errorf("sentiment must be up or down")
	}

	var roomID *uint
	roomSlug := strings.TrimSpace(input.RoomSlug)
	if roomSlug != "" {
		var room Room
		if err := db.Where("slug = ?", roomSlug).First(&room).Error; err == nil {
			roomID = &room.ID
			roomSlug = room.Slug
		}
	}

	entry := FeedbackEntry{
		RoomID:       roomID,
		RoomSlug:     roomSlug,
		ShareID:      strings.TrimSpace(input.ShareID),
		PromptFamily: promptFamily,
		Sentiment:    sentiment,
		Message:      truncateString(strings.TrimSpace(input.Message), 1000),
		Route:        truncateString(strings.TrimSpace(input.Route), 200),
		MetadataJSON: mustEncodeAnyJSON(input.Metadata),
		CreatedAt:    time.Now().UTC(),
	}
	return db.Create(&entry).Error
}

func (service *Service) CreateSoloPlanSnapshot(
	ctx context.Context,
	input SoloPlanCreateInput,
) (*SoloPlanSnapshotView, error) {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return nil, err
	}

	if len(input.Climbs) == 0 {
		return nil, fmt.Errorf("at least one climb is required")
	}
	if input.ProviderID == "" {
		return nil, fmt.Errorf("provider id is required")
	}

	shareID, err := security.NewOpaqueToken()
	if err != nil {
		return nil, err
	}

	createdAt := time.Now().UTC()
	snapshot := SoloPlanSnapshot{
		ShareID:     shareID,
		ProviderID:  string(input.ProviderID),
		Title:       truncateString(strings.TrimSpace(input.Title), 120),
		Notes:       truncateString(strings.TrimSpace(input.Notes), 2000),
		SurfaceID:   input.Surface.ID,
		SurfaceName: truncateString(strings.TrimSpace(input.Surface.Name), 120),
		SurfaceKind: truncateString(strings.TrimSpace(input.Surface.Kind), 60),
		ContextJSON: mustEncodeStringMap(input.Context),
		FiltersJSON: mustEncodeStringMap(input.Filters),
		ClimbsJSON:  mustEncodeProviderClimbs(input.Climbs),
		OpenPath:    truncateString(strings.TrimSpace(input.OpenPath), 400),
		CreatedBy:   truncateString(strings.TrimSpace(input.CreatedBy), 80),
		CreatedAt:   createdAt,
		UpdatedAt:   createdAt,
	}
	if snapshot.Title == "" {
		snapshot.Title = defaultSoloPlanTitle(input)
	}

	if err := db.Create(&snapshot).Error; err != nil {
		return nil, err
	}

	view := decodeSoloPlanSnapshot(snapshot)
	return &view, nil
}

func (service *Service) GetSoloPlanByShareID(
	ctx context.Context,
	shareID string,
) (*SoloPlanSnapshotView, error) {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return nil, err
	}

	var snapshot SoloPlanSnapshot
	if err := db.Where("share_id = ?", strings.TrimSpace(shareID)).First(&snapshot).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrRoomNotFound
		}
		return nil, err
	}

	view := decodeSoloPlanSnapshot(snapshot)
	return &view, nil
}

func (service *Service) GetRecapByShareID(
	ctx context.Context,
	shareID string,
) (*RoomRecapView, error) {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return nil, err
	}

	var recap RoomSessionRecap
	if err := db.Where("share_id = ?", strings.TrimSpace(shareID)).First(&recap).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrRoomNotFound
		}
		return nil, err
	}

	var payload RoomRecapView
	if err := json.Unmarshal([]byte(recap.PayloadJSON), &payload); err != nil {
		return nil, err
	}
	return &payload, nil
}

func (service *Service) ProductMetrics(ctx context.Context) (*ProductMetricsView, error) {
	db, err := mustStoreDB(service.store, ctx)
	if err != nil {
		return nil, err
	}

	view := &ProductMetricsView{
		Status:        "ok",
		GeneratedAt:   time.Now().UTC(),
		RetentionDays: int(analyticsRetentionTTL / (24 * time.Hour)),
	}

	if err := db.Model(&AnalyticsEvent{}).Count(&view.TotalEvents).Error; err != nil {
		return nil, err
	}
	if err := db.Model(&RoomSessionRecap{}).Count(&view.TotalRecaps).Error; err != nil {
		return nil, err
	}
	if err := db.Model(&SoloPlanSnapshot{}).Count(&view.TotalPlans).Error; err != nil {
		return nil, err
	}
	if err := db.Model(&FeedbackEntry{}).Count(&view.TotalFeedback).Error; err != nil {
		return nil, err
	}

	eventRows := make([]groupedCountRow, 0)
	if err := db.Model(&AnalyticsEvent{}).
		Select("event_name as key, COUNT(*) as count").
		Where("created_at >= ?", time.Now().UTC().Add(-7*24*time.Hour)).
		Group("event_name").
		Order("count DESC, key ASC").
		Scan(&eventRows).Error; err != nil {
		return nil, err
	}
	view.EventsLast7Days = toProductBreakdownView(eventRows)

	sentimentRows := make([]groupedCountRow, 0)
	if err := db.Model(&FeedbackEntry{}).
		Select("sentiment as key, COUNT(*) as count").
		Group("sentiment").
		Order("count DESC, key ASC").
		Scan(&sentimentRows).Error; err != nil {
		return nil, err
	}
	view.FeedbackSentiment = toProductBreakdownView(sentimentRows)

	promptRows := make([]groupedCountRow, 0)
	if err := db.Model(&FeedbackEntry{}).
		Select("prompt_family as key, COUNT(*) as count").
		Group("prompt_family").
		Order("count DESC, key ASC").
		Scan(&promptRows).Error; err != nil {
		return nil, err
	}
	view.FeedbackByPrompt = toProductBreakdownView(promptRows)

	return view, nil
}

func (service *Service) PruneAnalyticsEvents(ctx context.Context) error {
	if service.store == nil {
		return nil
	}

	cutoff := time.Now().UTC().Add(-analyticsRetentionTTL)
	return service.store.WithContext(ctx).
		Where("created_at < ?", cutoff).
		Delete(&AnalyticsEvent{}).Error
}

func toProductBreakdownView(rows []groupedCountRow) []ProductBreakdownView {
	result := make([]ProductBreakdownView, 0, len(rows))
	for _, row := range rows {
		result = append(result, ProductBreakdownView(row))
	}
	return result
}

func defaultSoloPlanTitle(input SoloPlanCreateInput) string {
	parts := []string{titleCase(string(input.ProviderID))}
	if name := strings.TrimSpace(input.Surface.Name); name != "" {
		parts = append(parts, name)
	}
	return strings.Join(parts, " · ")
}

func truncateString(value string, maxLength int) string {
	if maxLength <= 0 || len(value) <= maxLength {
		return value
	}
	return value[:maxLength]
}

func decodeSoloPlanSnapshot(snapshot SoloPlanSnapshot) SoloPlanSnapshotView {
	return SoloPlanSnapshotView{
		ShareID:    snapshot.ShareID,
		ProviderID: providers.ProviderID(snapshot.ProviderID),
		Title:      snapshot.Title,
		Notes:      snapshot.Notes,
		Surface: providers.ProviderSurface{
			ID:   snapshot.SurfaceID,
			Name: snapshot.SurfaceName,
			Kind: snapshot.SurfaceKind,
			Meta: decodeContextMap(snapshot.ContextJSON),
		},
		Filters:   decodeStringMap(snapshot.FiltersJSON),
		Climbs:    decodeProviderClimbs(snapshot.ClimbsJSON),
		OpenPath:  snapshot.OpenPath,
		CreatedBy: snapshot.CreatedBy,
		CreatedAt: snapshot.CreatedAt,
	}
}

func mustEncodeAnyJSON(value any) string {
	if value == nil {
		return "{}"
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return "{}"
	}
	return string(encoded)
}

func mustEncodeStringMap(value map[string]string) string {
	if len(value) == 0 {
		return "{}"
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		return "{}"
	}
	return string(encoded)
}

func mustEncodeProviderClimbs(climbs []providers.ProviderClimb) string {
	encoded, err := json.Marshal(climbs)
	if err != nil {
		return "[]"
	}
	return string(encoded)
}

func decodeProviderClimbs(raw string) []providers.ProviderClimb {
	if strings.TrimSpace(raw) == "" {
		return []providers.ProviderClimb{}
	}
	var climbs []providers.ProviderClimb
	if err := json.Unmarshal([]byte(raw), &climbs); err != nil {
		return []providers.ProviderClimb{}
	}
	return climbs
}

func (service *Service) persistRoomRecap(
	tx *gorm.DB,
	room *Room,
	summary RoomSessionSummary,
	participants []RoomParticipant,
	events []AnalyticsEvent,
) error {
	if tx == nil || room == nil {
		return nil
	}

	recap := buildRoomRecapPayload(room, summary, participants, events)
	payloadJSON := mustEncodeAnyJSON(recap)
	row := RoomSessionRecap{
		RoomID:      room.ID,
		ShareID:     summary.RecapShareID,
		RoomSlug:    room.Slug,
		PayloadJSON: payloadJSON,
		ClosedAt:    summary.ClosedAt,
		CreatedAt:   time.Now().UTC(),
		UpdatedAt:   time.Now().UTC(),
	}

	var existing RoomSessionRecap
	if err := tx.Where("room_id = ?", room.ID).First(&existing).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return tx.Create(&row).Error
		}
		return err
	}

	return tx.Model(&existing).Updates(map[string]any{
		"share_id":     row.ShareID,
		"room_slug":    row.RoomSlug,
		"payload_json": row.PayloadJSON,
		"closed_at":    row.ClosedAt,
		"updated_at":   time.Now().UTC(),
	}).Error
}

func buildRoomRecapPayload(
	room *Room,
	summary RoomSessionSummary,
	participants []RoomParticipant,
	events []AnalyticsEvent,
) RoomRecapView {
	summaryView := sessionSummaryView(summary)
	topVoted := summaryView.TopVoted
	finalQueue := summaryView.FinalQueue
	finalists := summaryView.Finalists

	participantNames := make([]string, 0, len(participants))
	readyCount := 0
	for _, participant := range participants {
		participantNames = append(participantNames, participant.DisplayName)
		if normalizeParticipantStatus(participant.Status) == participantStatusReady {
			readyCount++
		}
	}
	sort.Strings(participantNames)

	eventCounts := map[string]int{}
	for _, event := range events {
		eventCounts[event.EventName]++
	}

	heroClimb := featuredClimbFromSummary(topVoted, finalQueue, finalists)
	rematchClimbs := buildRematchClimbs(summaryView)

	slides := []RecapSlideView{
		{
			ID:          "hero",
			Eyebrow:     "Session hero",
			Title:       firstNonEmpty(summary.RoomName, fmt.Sprintf("Room %s", summary.RoomSlug)),
			Description: recapHeroDescription(summaryView, heroClimb),
			Stats: []RecapStatView{
				{Label: "Crew", Value: fmt.Sprintf("%d climbers", summary.ParticipantCount)},
				{Label: "Queue", Value: fmt.Sprintf("%d climbs", len(finalQueue))},
				{Label: "Ready", Value: fmt.Sprintf("%d marked ready", readyCount)},
			},
			FeaturedClimb: heroClimb,
		},
		{
			ID:          "momentum",
			Eyebrow:     "Momentum",
			Title:       "How the session moved",
			Description: "A programmatic read of how the room warmed up, voted, and narrowed the queue.",
			Stats: []RecapStatView{
				{Label: "Queue adds", Value: fmt.Sprintf("%d", eventCounts["room.queue.add"])},
				{Label: "Votes", Value: fmt.Sprintf("%d", eventCounts["room.vote.toggle"])},
				{Label: "Finalists", Value: fmt.Sprintf("%d", len(finalists))},
			},
		},
		{
			ID:          "hype",
			Eyebrow:     "Hype",
			Title:       "What the room wanted most",
			Description: "Top-voted climbs are preserved from the closed session snapshot, not live provider data.",
			Climbs:      topVotedSlice(topVoted, 3),
		},
		{
			ID:          "session-route",
			Eyebrow:     "Session route",
			Title:       "How the queue finished",
			Description: "The final queue order at room close, including the current and next markers when they existed.",
			Climbs:      topVotedSlice(finalQueue, 4),
		},
		{
			ID:           "crew",
			Eyebrow:      "Crew contributions",
			Title:        "Who shaped the night",
			Description:  "Participants who joined the room before close are captured here even if they later went offline.",
			Participants: participantNames,
			Stats:        buildCrewStats(finalQueue, finalists),
		},
		{
			ID:          "encore",
			Eyebrow:     "Encore",
			Title:       "Run it back",
			Description: "Start another room from the strongest climbs in this recap or pass the link around first.",
			Climbs:      topVotedSlice(topVotedSlice(finalQueue, 3), 3),
			Stats: []RecapStatView{
				{Label: "Recap link", Value: summary.RecapShareID},
				{Label: "Shared surface", Value: firstNonEmpty(summary.SurfaceName, "No surface captured")},
			},
		},
	}

	var rematchSeed *RoomSeedView
	if room.SurfaceID != "" && len(rematchClimbs) > 0 {
		rematchSeed = &RoomSeedView{
			ProviderID: providers.ProviderID(room.ProviderID),
			Surface: providers.ProviderSurface{
				ID:          room.SurfaceID,
				Name:        room.SurfaceName,
				Kind:        room.SurfaceKind,
				Description: room.SurfaceDescription,
				Meta:        decodeContextMap(room.SurfaceContextJSON),
			},
			Climbs: rematchClimbs,
		}
	}

	return RoomRecapView{
		ShareID:     summary.RecapShareID,
		RoomSlug:    summary.RoomSlug,
		RoomName:    summary.RoomName,
		ProviderID:  providers.ProviderID(summary.ProviderID),
		SurfaceName: summary.SurfaceName,
		ClosedAt:    summary.ClosedAt,
		Slides:      slides,
		RematchSeed: rematchSeed,
	}
}

func recapHeroDescription(
	summary SessionSummaryView,
	heroClimb *providers.ProviderClimb,
) string {
	if heroClimb == nil {
		return "This session closed without a standout climb, but the room recap is still preserved as a snapshot."
	}

	if topVote := firstVoteCount(summary.TopVoted); topVote > 0 {
		return fmt.Sprintf("%s led the room with %d vote%s.", heroClimb.Name, topVote, pluralSuffix(topVote))
	}

	return fmt.Sprintf("%s carried the most visible session momentum.", heroClimb.Name)
}

func buildCrewStats(
	finalQueue []SessionSummaryClimbView,
	finalists []SessionSummaryClimbView,
) []RecapStatView {
	counts := map[string]int{}
	for _, entry := range finalQueue {
		if entry.AddedBy != "" {
			counts[entry.AddedBy]++
		}
	}
	for _, entry := range finalists {
		if entry.AddedBy != "" {
			counts[entry.AddedBy]++
		}
	}

	type nameCount struct {
		Name  string
		Count int
	}
	items := make([]nameCount, 0, len(counts))
	for name, count := range counts {
		items = append(items, nameCount{Name: name, Count: count})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].Count != items[j].Count {
			return items[i].Count > items[j].Count
		}
		return items[i].Name < items[j].Name
	})

	stats := make([]RecapStatView, 0, minInt(len(items), 3))
	for _, item := range items[:minInt(len(items), 3)] {
		stats = append(stats, RecapStatView{
			Label: item.Name,
			Value: fmt.Sprintf("%d picks", item.Count),
		})
	}
	if len(stats) == 0 {
		stats = append(stats, RecapStatView{
			Label: "Room data",
			Value: "No queue or finalist ownership was captured",
		})
	}
	return stats
}

func buildRematchClimbs(summary SessionSummaryView) []providers.ProviderClimb {
	seed := make([]providers.ProviderClimb, 0, 4)
	seen := map[string]struct{}{}
	appendUnique := func(items []SessionSummaryClimbView, limit int) {
		for _, item := range items {
			if len(seed) >= limit {
				return
			}
			if item.Climb.ID == "" {
				continue
			}
			if _, ok := seen[item.Climb.ID]; ok {
				continue
			}
			seen[item.Climb.ID] = struct{}{}
			seed = append(seed, item.Climb)
		}
	}
	appendUnique(summary.FinalQueue, 4)
	appendUnique(summary.TopVoted, 4)
	return seed
}

func featuredClimbFromSummary(
	topVoted []SessionSummaryClimbView,
	finalQueue []SessionSummaryClimbView,
	finalists []SessionSummaryClimbView,
) *providers.ProviderClimb {
	for _, collection := range [][]SessionSummaryClimbView{topVoted, finalQueue, finalists} {
		if len(collection) == 0 || collection[0].Climb.ID == "" {
			continue
		}
		climb := collection[0].Climb
		return &climb
	}
	return nil
}

func topVotedSlice(items []SessionSummaryClimbView, limit int) []SessionSummaryClimbView {
	if limit <= 0 || len(items) == 0 {
		return []SessionSummaryClimbView{}
	}
	if len(items) <= limit {
		return items
	}
	return items[:limit]
}

func firstVoteCount(items []SessionSummaryClimbView) int {
	if len(items) == 0 {
		return 0
	}
	return items[0].VoteCount
}

func pluralSuffix(count int) string {
	if count == 1 {
		return ""
	}
	return "s"
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func minInt(left int, right int) int {
	if left < right {
		return left
	}
	return right
}

func titleCase(value string) string {
	if value == "" {
		return ""
	}
	return strings.ToUpper(value[:1]) + value[1:]
}

func buildAssistantState(
	room *Room,
	snapshot *RoomSnapshot,
) AssistantStateView {
	mode := assistantModeManual
	if room != nil {
		mode = normalizeAssistantMode(room.AssistantMode)
	}
	state := AssistantStateView{Mode: mode}
	if snapshot == nil || mode != assistantModeAssist {
		return state
	}

	readyCount := 0
	for _, participant := range snapshot.Participants {
		if participant.Status == participantStatusReady {
			readyCount++
		}
	}
	if readyCount == 0 {
		state.Message = "Waiting for someone in the room to mark ready."
		return state
	}

	currentClimbID := ""
	if snapshot.CurrentClimb != nil {
		currentClimbID = snapshot.CurrentClimb.ID
	}

	candidateFromSummary := func(items []SessionSummaryClimbView, source string) *AssistantSuggestionView {
		for _, item := range items {
			if item.Climb.ID == "" || item.Climb.ID == currentClimbID {
				continue
			}
			return &AssistantSuggestionView{
				Source:     source,
				ReadyCount: readyCount,
				Climb:      item.Climb,
			}
		}
		return nil
	}

	finalists := make([]SessionSummaryClimbView, 0, len(snapshot.Finalists))
	for _, entry := range snapshot.Finalists {
		finalists = append(finalists, SessionSummaryClimbView{
			Position: entry.Position,
			AddedBy:  entry.AddedBy,
			Climb:    entry.Climb,
		})
	}
	if suggestion := candidateFromSummary(finalists, "finalists"); suggestion != nil {
		state.Suggestion = suggestion
		state.Message = "Suggested from the finalists list."
		return state
	}

	topVoted := buildTopVotedSnapshotItems(snapshot)
	if suggestion := candidateFromSummary(topVoted, "top_voted"); suggestion != nil {
		state.Suggestion = suggestion
		state.Message = "Suggested from the current top-voted climbs."
		return state
	}

	queue := make([]SessionSummaryClimbView, 0, len(snapshot.Queue))
	for _, entry := range snapshot.Queue {
		queue = append(queue, SessionSummaryClimbView{
			Position: entry.Position,
			Status:   entry.Status,
			AddedBy:  entry.AddedBy,
			Climb:    entry.Climb,
		})
	}
	if suggestion := candidateFromSummary(queue, "queue"); suggestion != nil {
		state.Suggestion = suggestion
		state.Message = "Suggested from the remaining queue."
		return state
	}

	state.Message = "No eligible suggestion is available yet."
	return state
}

func buildTopVotedSnapshotItems(snapshot *RoomSnapshot) []SessionSummaryClimbView {
	if snapshot == nil {
		return []SessionSummaryClimbView{}
	}

	byID := map[string]providers.ProviderClimb{}
	for _, entry := range snapshot.Finalists {
		byID[entry.Climb.ID] = entry.Climb
	}
	for _, entry := range snapshot.Queue {
		byID[entry.Climb.ID] = entry.Climb
	}
	if snapshot.CurrentClimb != nil {
		byID[snapshot.CurrentClimb.ID] = *snapshot.CurrentClimb
	}

	items := make([]SessionSummaryClimbView, 0, len(snapshot.VoteCounts))
	for climbID, voteCount := range snapshot.VoteCounts {
		if voteCount <= 0 {
			continue
		}
		climb, ok := byID[climbID]
		if !ok {
			continue
		}
		items = append(items, SessionSummaryClimbView{
			VoteCount: voteCount,
			Climb:     climb,
		})
	}
	sort.Slice(items, func(i, j int) bool {
		if items[i].VoteCount != items[j].VoteCount {
			return items[i].VoteCount > items[j].VoteCount
		}
		return items[i].Climb.Name < items[j].Climb.Name
	})
	return items
}
