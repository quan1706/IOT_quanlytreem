package com.babyguard.server.model;

public class TelegramAction {
    private String performer;
    private String action;
    private String result;
    private String timestamp;

    public TelegramAction(String performer, String action, String result) {
        this.performer = performer;
        this.action = action;
        this.result = result;
        this.timestamp = java.time.LocalDateTime.now().format(java.time.format.DateTimeFormatter.ofPattern("HH:mm:ss"));
    }

    public String getPerformer() {
        return performer;
    }

    public String getAction() {
        return action;
    }

    public String getResult() {
        return result;
    }

    public String getTimestamp() {
        return timestamp;
    }

    @Override
    public String toString() {
        return String.format("[%s] - %s - %s - %s", timestamp, performer, action, result);
    }
}
