const headers = {
	UserAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
	Origin: "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg"
};
 
const socket = new WebSocket(
    "wss://proxy2.wynd.network:4444/", null, {
		headers: headers
	}
);

const device_id = crypto.randomUUID();
const getTimestamp = () => Math.floor(Date.now() / 1000);

socket.onopen = async function(_) {
    while (true) {
	    let msg = {
		   id: device_id,
		   version: "1.0.0",
		   action: "PING",
		   data: {}
		}
		socket.send(JSON.stringify(msg));
		await new Promise(r => setTimeout(r, 60000));
	}
}
 
socket.onmessage = function(event) {
	let message = JSON.parse(event.data);
	if (message.action == "AUTH") {
	    let auth_response = {
			id: message.id,
			origin_action: "AUTH",
			result: {
				browser_id: device_id,
				user_id: "2ohgfjwsOCf1p0zstTE6Y0N5zSs",
			    user_agent: headers.UserAgent,
				timestamp: getTimestamp(),
				device_type: "extension",
				version: "4.64.2",
				extension_id: "ilehaonighjijnmpnagapkhpcdbhclfg"
			}
		}
		socket.send(JSON.stringify(auth_response));
	} else if (message.action == "PONG") {
		let pong_response = {
			id: message.id,
			origin_action: "PONG"
		}
		socket.send(JSON.stringify(pong_response));
	}
}