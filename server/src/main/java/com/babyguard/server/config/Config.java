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
            } else {
                prop.load(input);
            }

            BOT_USERNAME = System.getenv("BOT_USERNAME");
            if (BOT_USERNAME == null)
                BOT_USERNAME = prop.getProperty("bot.username");

            TELEGRAM_BOT_TOKEN = System.getenv("BOT_TOKEN");
            if (TELEGRAM_BOT_TOKEN == null)
                TELEGRAM_BOT_TOKEN = prop.getProperty("bot.token");

            TELEGRAM_CHAT_ID = System.getenv("CHAT_ID");
            if (TELEGRAM_CHAT_ID == null)
                TELEGRAM_CHAT_ID = prop.getProperty("chat.id");

            ESP32_IP = System.getenv("ESP32_IP");
            if (ESP32_IP == null)
                ESP32_IP = prop.getProperty("esp32.ip");

            LogService.addLog("[Config] Cấu hình Ready: Bot=" + BOT_USERNAME + ", IP=" + ESP32_IP);
            ESP32_COMMAND_URL = "http://" + ESP32_IP + "/command";
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
