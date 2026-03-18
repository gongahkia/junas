import Flutter
import MultipeerConnectivity

class MultipeerPlugin: NSObject, MCSessionDelegate, MCNearbyServiceAdvertiserDelegate, MCNearbyServiceBrowserDelegate, FlutterStreamHandler {
    private var eventSink: FlutterEventSink?
    private var localPeerId: MCPeerID?
    private var session: MCSession?
    private var advertiser: MCNearbyServiceAdvertiser?
    private var browser: MCNearbyServiceBrowser?
    private var connectedPeers: [String: MCPeerID] = [:]
    private var peerDisplayNames: [String: String] = [:]
    private var discoveredMCPeers: [String: MCPeerID] = [:]

    func register(with messenger: FlutterBinaryMessenger) {
        let method = FlutterMethodChannel(name: "kilter_together/multipeer", binaryMessenger: messenger)
        let event = FlutterEventChannel(name: "kilter_together/multipeer_events", binaryMessenger: messenger)
        method.setMethodCallHandler { [weak self] call, result in
            self?.handle(call, result: result)
        }
        event.setStreamHandler(self)
    }

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        let args = call.arguments as? [String: Any] ?? [:]
        switch call.method {
        case "startAdvertising":
            startAdvertising(displayName: args["displayName"] as? String ?? "Host",
                           serviceId: args["serviceId"] as? String ?? "kilter-p2p",
                           result: result)
        case "stopAdvertising":
            advertiser?.stopAdvertisingPeer(); advertiser = nil; result(nil)
        case "startDiscovery":
            startDiscovery(serviceId: args["serviceId"] as? String ?? "kilter-p2p", result: result)
        case "stopDiscovery":
            browser?.stopBrowsingForPeers(); browser = nil; result(nil)
        case "connectToPeer":
            connectToPeer(peerId: args["peerId"] as? String ?? "",
                        displayName: args["displayName"] as? String ?? "", result: result)
        case "disconnectFromPeer":
            let pid = args["peerId"] as? String ?? ""
            connectedPeers.removeValue(forKey: pid); peerDisplayNames.removeValue(forKey: pid); result(nil)
        case "disconnectAll":
            session?.disconnect(); connectedPeers.removeAll(); peerDisplayNames.removeAll(); result(nil)
        case "send":
            sendData(peerId: args["peerId"] as? String ?? "",
                    data: (args["data"] as? FlutterStandardTypedData)?.data ?? Data(), result: result)
        case "broadcast":
            broadcastData(data: (args["data"] as? FlutterStandardTypedData)?.data ?? Data(), result: result)
        case "getConnectedPeers":
            let peers = connectedPeers.map { ["id": $0.key, "displayName": peerDisplayNames[$0.key] ?? $0.value.displayName] }
            result(peers)
        default:
            result(FlutterMethodNotImplemented)
        }
    }

    private func ensureSession(displayName: String) {
        if localPeerId == nil || localPeerId!.displayName != displayName {
            localPeerId = MCPeerID(displayName: displayName)
            session = MCSession(peer: localPeerId!, securityIdentity: nil, encryptionPreference: .none)
            session?.delegate = self
            connectedPeers.removeAll(); peerDisplayNames.removeAll()
        }
    }

    private func sanitizeServiceType(_ raw: String) -> String {
        let filtered = raw.lowercased().filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "." }
        let cleaned = filtered.replacingOccurrences(of: ".", with: "-")
        let trimmed = String(cleaned.prefix(15))
        return trimmed.isEmpty ? "kilter-p2p" : trimmed
    }

    private func startAdvertising(displayName: String, serviceId: String, result: @escaping FlutterResult) {
        ensureSession(displayName: displayName)
        let st = sanitizeServiceType(serviceId)
        advertiser = MCNearbyServiceAdvertiser(peer: localPeerId!, discoveryInfo: ["name": displayName], serviceType: st)
        advertiser?.delegate = self
        advertiser?.startAdvertisingPeer()
        result(nil)
    }

    private func startDiscovery(serviceId: String, result: @escaping FlutterResult) {
        if localPeerId == nil { ensureSession(displayName: "Guest-\(UUID().uuidString.prefix(4))") }
        let st = sanitizeServiceType(serviceId)
        browser = MCNearbyServiceBrowser(peer: localPeerId!, serviceType: st)
        browser?.delegate = self
        browser?.startBrowsingForPeers()
        result(nil)
    }

    private func connectToPeer(peerId: String, displayName: String, result: @escaping FlutterResult) {
        guard let mcPeer = discoveredMCPeers[peerId] else {
            result(FlutterError(code: "peer_not_found", message: "Peer not found: \(peerId)", details: nil)); return
        }
        guard let session = session else {
            result(FlutterError(code: "no_session", message: "No active session", details: nil)); return
        }
        browser?.invitePeer(mcPeer, to: session, withContext: nil, timeout: 30)
        result(nil)
    }

    private func sendData(peerId: String, data: Data, result: @escaping FlutterResult) {
        guard let mcPeer = connectedPeers[peerId] else {
            result(FlutterError(code: "peer_not_found", message: "Peer not connected: \(peerId)", details: nil)); return
        }
        do { try session?.send(data, toPeers: [mcPeer], with: .reliable); result(nil) }
        catch { result(FlutterError(code: "send_failed", message: error.localizedDescription, details: nil)) }
    }

    private func broadcastData(data: Data, result: @escaping FlutterResult) {
        guard let session = session, !session.connectedPeers.isEmpty else { result(nil); return }
        do { try session.send(data, toPeers: session.connectedPeers, with: .reliable); result(nil) }
        catch { result(FlutterError(code: "broadcast_failed", message: error.localizedDescription, details: nil)) }
    }

    private func peerKey(_ peer: MCPeerID) -> String { peer.displayName }

    private func emitEvent(_ event: [String: Any]) {
        DispatchQueue.main.async { [weak self] in self?.eventSink?(event) }
    }

    // MARK: - MCSessionDelegate
    func session(_ session: MCSession, peer peerID: MCPeerID, didChange state: MCSessionState) {
        let key = peerKey(peerID)
        switch state {
        case .connected:
            connectedPeers[key] = peerID; peerDisplayNames[key] = peerID.displayName
            emitEvent(["type": "connected", "peerId": key, "displayName": peerID.displayName])
        case .notConnected:
            connectedPeers.removeValue(forKey: key); peerDisplayNames.removeValue(forKey: key)
            emitEvent(["type": "disconnected", "peerId": key, "displayName": peerID.displayName])
        case .connecting: break
        @unknown default: break
        }
    }
    func session(_ session: MCSession, didReceive data: Data, fromPeer peerID: MCPeerID) {
        emitEvent(["type": "data", "peerId": peerKey(peerID), "data": FlutterStandardTypedData(bytes: data)])
    }
    func session(_ session: MCSession, didReceive stream: InputStream, withName streamName: String, fromPeer peerID: MCPeerID) {}
    func session(_ session: MCSession, didStartReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, with progress: Progress) {}
    func session(_ session: MCSession, didFinishReceivingResourceWithName resourceName: String, fromPeer peerID: MCPeerID, at localURL: URL?, withError error: Error?) {}

    // MARK: - MCNearbyServiceAdvertiserDelegate
    func advertiser(_ advertiser: MCNearbyServiceAdvertiser, didReceiveInvitationFromPeer peerID: MCPeerID, withContext context: Data?, invitationHandler: @escaping (Bool, MCSession?) -> Void) {
        invitationHandler(true, session)
    }
    func advertiser(_ advertiser: MCNearbyServiceAdvertiser, didNotStartAdvertisingPeer error: Error) {
        emitEvent(["type": "error", "message": "Advertising failed: \(error.localizedDescription)"])
    }

    // MARK: - MCNearbyServiceBrowserDelegate
    func browser(_ browser: MCNearbyServiceBrowser, foundPeer peerID: MCPeerID, withDiscoveryInfo info: [String: String]?) {
        let key = peerKey(peerID)
        discoveredMCPeers[key] = peerID
        let displayName = info?["name"] ?? peerID.displayName
        peerDisplayNames[key] = displayName
        emitEvent(["type": "peerFound", "peerId": key, "displayName": displayName])
    }
    func browser(_ browser: MCNearbyServiceBrowser, lostPeer peerID: MCPeerID) {
        let key = peerKey(peerID); discoveredMCPeers.removeValue(forKey: key)
        emitEvent(["type": "peerLost", "peerId": key])
    }
    func browser(_ browser: MCNearbyServiceBrowser, didNotStartBrowsingForPeers error: Error) {
        emitEvent(["type": "error", "message": "Discovery failed: \(error.localizedDescription)"])
    }

    // MARK: - FlutterStreamHandler
    func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
        eventSink = events; return nil
    }
    func onCancel(withArguments arguments: Any?) -> FlutterError? {
        eventSink = nil; return nil
    }
}
