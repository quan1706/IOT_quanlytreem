package com.iot.babycry.listener;

import com.iot.babycry.bot.BabyCryTelegramBot;
import com.iot.babycry.service.Esp32Service;
import jakarta.servlet.ServletContext;
import jakarta.servlet.ServletContextEvent;
import jakarta.servlet.ServletContextListener;
import jakarta.servlet.annotation.WebListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.telegram.telegrambots.meta.TelegramBotsApi;
import org.telegram.telegrambots.updatesreceivers.DefaultBotSession;
import java.io.InputStream;
import java.util.Properties;

@WebListener
public class AppContextListener implements ServletContextListener {
    private static final Logger log = LoggerFactory.getLogger(AppContextListener.class);

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        ServletContext ctx = sce.getServletContext();
        log.info("Initializing Application Context...");

        try (InputStream input = ctx.getResourceAsStream("/WEB-INF/classes/application.properties")) {
            Properties prop = new Properties();
            if (input == null) {
                log.error("Sorry, unable to find application.properties");
                return;
            }
            prop.load(input);

            String botUsername = System.getenv("BOT_USERNAME");
            if (botUsername == null)
                botUsername = prop.getProperty("bot.username");

            String botToken = System.getenv("BOT_TOKEN");
            if (botToken == null)
                botToken = prop.getProperty("bot.token");

            String esp32Url = System.getenv("ESP32_URL");
            if (esp32Url == null)
                esp32Url = prop.getProperty("esp32.url");

            Esp32Service esp32Service = new Esp32Service(esp32Url);
            BabyCryTelegramBot bot = new BabyCryTelegramBot(botUsername, botToken, esp32Service);

            TelegramBotsApi botsApi = new TelegramBotsApi(DefaultBotSession.class);
            botsApi.registerBot(bot);

            ctx.setAttribute("telegramBot", bot);
            ctx.setAttribute("esp32Service", esp32Service);

            log.info("Application Context Initialized successfully.");
        } catch (Exception e) {
            log.error("Error during Context Initialization: {}", e.getMessage());
        }
    }

    @Override
    public void contextDestroyed(ServletContextEvent sce) {
        log.info("Application Context Destroyed.");
    }
}
