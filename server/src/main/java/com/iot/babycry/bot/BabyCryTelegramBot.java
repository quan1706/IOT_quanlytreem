package com.iot.babycry.bot;

import com.iot.babycry.service.Esp32Service;
import lombok.Getter;
import lombok.Setter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.send.SendPhoto;
import org.telegram.telegrambots.meta.api.objects.InputFile;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.io.ByteArrayInputStream;
import java.util.ArrayList;
import java.util.List;

@Getter
@Setter
public class BabyCryTelegramBot extends TelegramLongPollingBot {
    private static final Logger log = LoggerFactory.getLogger(BabyCryTelegramBot.class);

    private final String botUsername;
    private final String botToken;
    private final Esp32Service esp32Service;
    private String lastChatId;

    public BabyCryTelegramBot(String botUsername, String botToken, Esp32Service esp32Service) {
        this.botUsername = botUsername;
        this.botToken = botToken;
        this.esp32Service = esp32Service;
    }

    @Override
    public String getBotUsername() {
        return botUsername;
    }

    @Override
    public String getBotToken() {
        return botToken;
    }

    @Override
    public void onUpdateReceived(Update update) {
        if (update.hasMessage() && update.getMessage().hasText()) {
            String text = update.getMessage().getText();
            if (text.equals("/start")) {
                lastChatId = update.getMessage().getChatId().toString();
                log.info("Bot initialized with ChatID: {}", lastChatId);
                sendSimpleMessage(lastChatId, "Chào mừng bạn đến với Baby Cry Monitor! Tôi đã nhận được ID của bạn ("
                        + lastChatId + "). Tôi sẽ thông báo khi bé khóc.");
            }
        } else if (update.hasCallbackQuery()) {
            String callbackData = update.getCallbackQuery().getData();
            String chatId = update.getCallbackQuery().getMessage().getChatId().toString();
            handleCallback(chatId, callbackData);
        }
    }

    private void handleCallback(String chatId, String action) {
        switch (action) {
            case "ACTION_PLAY_MUSIC":
                esp32Service.sendCommand("phat_nhac");
                sendSimpleMessage(chatId, "🎵 Đang phát nhạc ru cho bé...");
                break;
            case "ACTION_SWING":
                esp32Service.sendCommand("ru_vong");
                sendSimpleMessage(chatId, "🔄 Đang khởi động chế độ ru võng...");
                break;
            case "ACTION_STOP":
                esp32Service.sendCommand("dung");
                sendSimpleMessage(chatId, "⏹ Đã dừng tất cả các hoạt động.");
                break;
            case "ACTION_CHECK":
                esp32Service.requestSnapshot();
                sendSimpleMessage(chatId, "📷 Đang yêu cầu chụp ảnh từ camera...");
                break;
        }
    }

    public void sendAlertWithPhoto(byte[] imageBytes) {
        if (lastChatId == null) {
            log.error("Cannot send alert. No ChatID recorded. Please send /start to the bot first.");
            return;
        }

        SendPhoto sendPhoto = new SendPhoto();
        sendPhoto.setChatId(lastChatId);
        sendPhoto.setPhoto(new InputFile(new ByteArrayInputStream(imageBytes), "baby_cry.jpg"));
        sendPhoto.setCaption("⚠️ Cảnh báo: Trẻ đang khóc! Chọn hành động:");
        sendPhoto.setReplyMarkup(createInlineKeyboard());

        try {
            execute(sendPhoto);
        } catch (TelegramApiException e) {
            log.error("Failed to send photo alert: {}", e.getMessage());
        }
    }

    private InlineKeyboardMarkup createInlineKeyboard() {
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup();
        List<List<InlineKeyboardButton>> rows = new ArrayList<>();

        List<InlineKeyboardButton> row1 = new ArrayList<>();
        row1.add(createButton("🎵 Phát nhạc", "ACTION_PLAY_MUSIC"));
        row1.add(createButton("🔄 Ru võng", "ACTION_SWING"));

        List<InlineKeyboardButton> row2 = new ArrayList<>();
        row2.add(createButton("⏹ Dừng", "ACTION_STOP"));
        row2.add(createButton("📷 Kiểm tra", "ACTION_CHECK"));

        rows.add(row1);
        rows.add(row2);
        markup.setKeyboard(rows);
        return markup;
    }

    private InlineKeyboardButton createButton(String text, String callbackData) {
        InlineKeyboardButton button = new InlineKeyboardButton();
        button.setText(text);
        button.setCallbackData(callbackData);
        return button;
    }

    private void sendSimpleMessage(String chatId, String text) {
        SendMessage message = new SendMessage();
        message.setChatId(chatId);
        message.setText(text);
        try {
            execute(message);
        } catch (TelegramApiException e) {
            log.error("Failed to send simple message: {}", e.getMessage());
        }
    }
}
