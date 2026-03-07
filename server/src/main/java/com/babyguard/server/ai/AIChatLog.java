package com.babyguard.server.ai;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public class AIChatLog {
    private String timestamp;
    private String userName;
    private String userMessage;
    private String aiAnalysis;
    private String status; // Pending, Executed, Cancelled

    public AIChatLog(String userName, String userMessage, String aiAnalysis) {
        this.timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss"));
        this.userName = userName;
        this.userMessage = userMessage;
        this.aiAnalysis = aiAnalysis;
        this.status = "Pending Confirmation";
    }

    public String getTimestamp() {
        return timestamp;
    }

    public String getUserName() {
        return userName;
    }

    public String getUserMessage() {
        return userMessage;
    }

    public String getAiAnalysis() {
        return aiAnalysis;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }
}
