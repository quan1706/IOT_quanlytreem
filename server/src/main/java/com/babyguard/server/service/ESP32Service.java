package com.babyguard.server.service;

import com.babyguard.server.config.Config;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import java.io.IOException;

public class ESP32Service {
    private final OkHttpClient client = new OkHttpClient();

    public void sendCommand(String command) {
        LogService.addFormattedLog("Server", "Gửi lệnh [" + command + "] cho ESP32", "Đang kết nối...");
        String json = "{\"cmd\":\"" + command + "\"}";
        LogService.addLog("[ESP32] SEND JSON: " + json);
        RequestBody body = RequestBody.create(json, MediaType.parse("application/json"));

        Request request = new Request.Builder()
                .url(Config.ESP32_COMMAND_URL)
                .post(body)
                .build();

        // Gửi async để không block thread xử lý của Telegram
        client.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                LogService.addFormattedLog("Server", "ESP32 phản hồi", "THẤT BẠI: " + e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                LogService.addFormattedLog("Server", "ESP32 phản hồi", "Thành công - Mã: " + response.code());
                response.close();
            }
        });
    }

    public void requestSnapshot() {
        sendCommand("snapshot");
    }
}
