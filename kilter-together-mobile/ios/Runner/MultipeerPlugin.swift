import Flutter
import MultipeerConnectivity

class MultipeerPlugin: NSObject, FlutterPlugin, MCSessionDelegate, MCNearbyServiceAdvertiserDelegate, MCNearbyServiceBrowserDelegate {
    private let methodChannel: FlutterMethodChannel
    private let eventChannel: FlutterEventChannel
    private var eventSink: FlutterEventSink?
    private var localPeerId: MCPeerID?
    private var session: MCSession?
    private var advertiser: MCNearbyServiceAdvertiser?
    private var browser: MCNearbyServiceBrowser?
    private var connectedPeers: [String: MCPeerID] = [:]
    private var peerDisplayNames: [String: String] = [:]

    static func register(with registrar: FlutterPluginRegistrar) {
        let method = FlutterMethodChannel(name: "kilter_together/multipeer", binaryMessenger: registrar.messenger())
        let event = FlutterEventChannel(name: "kilter_together/multipeer_events", binaryMessenger: registrar.messenger())
        let instance = MultipeerPlugin(methodChannel: method, eventChannel: event)
        registrar.addMethodCallDelegate(instance, channel: method)
        event.setStreamHandler(instance)
    }

    init(methodChannel: FlutterMethodChannel, eventChannel: FlutterEventChannel) {
        self.methodChannel = methodChannel
        self.eventChannel = eventChannel
        super.init()
    }

    func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
        let args = call.arguments as? [String: Any] ?? [:]
        switch call.method {
        case "startAdvertising":
            startAdvertising(displayName: args["displayName"] as? String ?? "Host",
                           serviceId: args["serviceId"] as? String ?? "kilter-p2p",
                           result: result)
        case "stopAdvertising":
            stopAdvertising(result: result)
        case "startDiscovery":
            startDiscovery(serviceId: args["serviceId"] as? String ?? "kilter-p2p",
                         result: result)
        case "stopDiscovery":
            stopDiscovery(result: result)
        case "connectToPeer":
            connectToPeer(peerId: args["peerId"] as? String ?? "",
                        displayName: args["displayName"] as? String ?? "",
                        result: result)
        case "disconnectFromPeer":
            disconnectFromPeer(peerId: args["peerId"] as? String ?? "", result: result)
        case "disconnectAll":
            disconnectAll(result: result)
        case "send":
            sendData(peerId: args["peerId"] as? String ?? "",
                    data: (args["data"] as? FlutterStandardTypedData)?.data ?? Data(),
                    result: result)
        case "broadcast":
            broadcastData(data: (args["data"] as? FlutterStandardTypedData)?.data ?? Data(),
                        result: result)
        case "getConnectedPeers":
            getConnectedPeers(result: result)
        default:
            result(FlutterMethodNotImplemented)
        }
    }

    private func ensureSession(displayName: String) {
        if localPeerId == nil || localPeerId!.displayName != displayName {
            localPeerId = MCPeerID(displayName: displayName)
            session = MCSession(peer: localPeerId!, securityIdentity: nil, encryptionPreference: .none)
            session?.delegate = self
            connectedPeers.removeAll()
            peerDisplayNames.removeAll()
        }
    }

    // sanitize service type: MCNearbyService requires 1-15 chars, lowercase+hyphen, start/end with letter
    private func sanitizeServiceType(_ raw: String) -> String {
        let filtered = raw.lowercased().filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "." }
        let cleaned = filtered.replacingOccurrences(of: ".", with: "-")
        let trimmed = String(cleaned.prefix(15))
        if trimmed.isEmpty { return "kilter-p2p" }
        return trimmed
    }

    private func startAdvertising(displayName: String, serviceId: String, result: @escaping FlutterResult) {
        ensureSession(displayName: displayName)
        let serviceType = sanitizeServiceType(serviceId)
        advertiser = MCNearbyServiceAdvertiser(peer: localPeerId!, discoveryInfo: ["name": displayName], serviceType: serviceType)
        advertiser?.delegate = self
        advertiser?.startAdvertisingPeer()
        result(nil)
    }

    private func stopAdvertising(result: @escaping FlutterResult) {
        advertiser?.stopAdvertisingPeer()
        advertiser = nil
        result(nil)
    }

    private func startDiscovery(serviceId: String, result: @escaping FlutterResult) {
        if localPeerId == nil {
            ensureSession(displayName: "Guest-\(UUID().uuidString.prefix(4))")
        }
        let serviceType = sanitizeServiceType(serviceId)
        browser = MCNearbyServiceBrowser(peer: localPeerId!, serviceType: serviceType)
        browser?.delegate = self
        browser?.startBrowsingForPeers()
        result(nil)
    }

    private func stopDiscovery(result: @escaping FlutterResult) {
        browser?.stopBrowsingForPeers()
        browser = nil
        result(nil)
    }

    private func connectToPeer(peerId: String, displayName: String, result: @escaping FlutterResult) {
        guard let mcPeer = connectedPeers[peerId] ?? findDiscoveredPeer(peerId) else {
            result(FlutterError(code: "peer_not_found", message: "Peer not found: \(peerId)", details: nil))
            return
        }
        guard let session = session else {
            result(FlutterError(code: "no_session", message: "No active session", details: nil))
            return
        }
        browser?.invitePeer(mcPeer, to: session, withContext: nil, timeout: 30)
        result(nil)
    }

    private func disconnectFromPeer(peerId: String, result: @escaping FlutterResult) {
        connectedPeers.removeValue(forKey: peerId)
        peerDisplayNames.removeValue(forKey: peerId)
        result(nil)
    }

    private func disconnectAll(result: @escaping FlutterResult) {
        session?.disconnect()
        connectedPeers.removeAll()
        peerDisplayNames.removeAll()
        result(nil)
    }

    private func sendData(peerId: String, data: Data, result: @escaping FlutterResult) {
        guard let mcPeer = connectedPeers[peerId] else {
            result(FlutterError(code: "peer_not_found", message: "Peer not connected: \(peerId)", details: nil))
            return
        }
        do {
            try session?.send(data, toPeers: [mcPeer], with: .reliable)
            result(nil)
        } catch {
            result(FlutterError(code: "send_failed", message: error.localizedDescription, details: nil))
        }
    }

    private func broadcastData(data: Data, result: @escaping FlutterResult) {
        guard let session = session, !session.connectedPeers.isEmpty else {
            result(nil)
            return
        }
        do {
            try session.send(data, toPeers: session.connectedPeers, with: .reliable)
            result(nil)
        } catch {
            result(FlutterError(code: "broadcast_failed", message: error.localizedDescription, details: nil))
        }
    }

    private func getConnectedPeers(result: @escaping FlutterResult) {
        let peers = connectedPeers.map { (key, value) -> [String: String] in
            ["id": key, "displayName": peerDisplayNames[key] ?? value.displayName]
        }
        result(peers)
    }

    private var discoveredMCPeers: [String: MCPeerID] = [:]

    private func findDiscoveredPeer(_ peerId: String) -> MCPeerID? {
        return discoveredMCPeers[peerId]
    }

    private func peerKey(_ peer: MCPeerID) -> String {
        return peer.displayName
    }

    private func emitEvent(_ event: [String: Any]) {
        DispatchQueue.main.async { [weak self] in
            self?.eventSink?(event)
        }
    }

    // MARK: - MCSessionDelegate

    func session(_ session: MCSession, peer peerID: MCPeerID, didChange state: MCSessionState) {
        let key = peerKey(peerID)
        switch state {
        case .connected:
            connectedPeers[key] = peerID
            peerDisplayNames[key] = peerID.displayName
            emitEvent(["type": "connected", "peerId": key, "displayName": peerID.displayName])
        case .notConnected:
            connectedPeers.removeValue(forKey: key)
            peerDisplayNames.removeValue(forKey: key)
            emitEvent(["type": "disconnected", "peerId": key, "displayName": peerID.displayName])
        case .connecting:
            break
        @unknown default:
            break
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
        // auto-accept all invitations
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
        let key = peerKey(peerID)
        discoveredMCPeers.removeValue(forKey: key)
        emitEvent(["type": "peerLost", "peerId": key])
    }

    func browser(_ browser: MCNearbyServiceBrowser, didNotStartBrowsingForPeers error: Error) {
        emitEvent(["type": "error", "message": "Discovery failed: \(error.localizedDescription)"])
    }
}

// MARK: - FlutterStreamHandler

extension MultipeerPlugin: FlutterStreamHandler {
    func onListen(withArguments arguments: Any?, eventSink events: @escaping FlutterEventSink) -> FlutterError? {
        eventSink = events
        return nil
    }

    func onCancel(withArguments arguments: Any?) -> FlutterError? {
        eventSink = nil
        return nil
    }
}
