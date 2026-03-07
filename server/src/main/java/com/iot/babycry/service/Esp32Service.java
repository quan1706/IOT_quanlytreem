package com.iot.babycry.service;

import lombok.Getter;
import lombok.Setter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Map;
import com.fasterxml.jackson.databind.ObjectMapper;

@Getter
@Setter
public class Esp32Service {
    private static final Logger log = LoggerFactory.getLogger(Esp32Service.class);
    private String esp32Url;
    private final HttpClient httpClient = HttpClient.newHttpClient();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public Esp32Service(String esp32Url) {
        this.esp32Url = esp32Url;
    }

    public void sendCommand(String command) {
        String url = esp32Url + "/command";
        Map<String, String> body = new HashMap<>();
        body.put("cmd", command);

        try {
            log.info("Sending command '{}' to ESP32 at {}", command, url);
            String jsonBody = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                    .build();

            httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                    .thenAccept(response -> {
                        if (response.statusCode() == 200) {
                            log.info("Successfully sent command {} to ESP32", command);
                        } else {
                            log.warn("Failed to send command to ESP32, Status: {}", response.statusCode());
                        }
                    });
        } catch (Exception e) {
            log.error("Failed to send command to ESP32: {}", e.getMessage());
        }
    }

    public void requestSnapshot() {
        sendCommand("kiem_tra");
    }
}
