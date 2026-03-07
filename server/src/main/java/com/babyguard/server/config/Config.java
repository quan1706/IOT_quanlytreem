package com.babyguard.server.config;

import com.babyguard.server.service.LogService;
import java.io.InputStream;
import java.util.Properties;

public class Config {
    public static String BOT_USERNAME;
    public static String TELEGRAM_BOT_TOKEN;
    public static String TELEGRAM_CHAT_ID;
    public static String ESP32_IP;
    public static String ESP32_COMMAND_URL;

    static {
        try (InputStream input = Config.class.getClassLoader().getResourceAsStream("application.properties")) {
            Properties prop = new Properties();
            if (input == null) {
                System.err.println("Sorry, unable to find application.properties. Using defaults.");
                // Fallback defaults
                TELEGRAM_BOT_TOKEN = "8765806795:AAEB83HSeGkpYYv0JsnnPz6IaiSCvlDOn_w";
                TELEGRAM_CHAT_ID = "-5283283687";
                ESP32_IP = "192.168.1.10";
            } else {
                prop.load(input);
                BOT_USERNAME = prop.getProperty("bot.username");
                TELEGRAM_BOT_TOKEN = prop.getProperty("bot.token");
                TELEGRAM_CHAT_ID = prop.getProperty("chat.id");
                ESP32_IP = prop.getProperty("esp32.ip");

                LogService.addLog("[Config] Đã tải cấu hình: Bot=" + BOT_USERNAME + ", ChatID=" + TELEGRAM_CHAT_ID);
            }
            ESP32_COMMAND_URL = "http://" + ESP32_IP + "/command";
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
