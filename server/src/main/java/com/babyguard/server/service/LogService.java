package com.babyguard.server.service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class LogService {
    private static final List<String> logs = Collections.synchronizedList(new ArrayList<>());
    private static final int MAX_LOGS = 50;
    private static final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("HH:mm:ss");

    public static void addLog(String message) {
        String timestamp = LocalDateTime.now().format(formatter);
        String logEntry = "[" + timestamp + "] " + message;

        logs.add(0, logEntry); // Add to top
        if (logs.size() > MAX_LOGS) {
            logs.remove(logs.size() - 1);
        }

        // Also print to console for backup
        System.out.println(logEntry);
    }

    public static void addFormattedLog(String performer, String action, String result) {
        String timestamp = LocalDateTime.now().format(formatter);
        // Format: [HH:mm:ss] - Performer - Action - Result
        String logEntry = String.format("[%s] - %s - %s - %s", timestamp, performer, action, result);

        logs.add(0, logEntry);
        if (logs.size() > MAX_LOGS) {
            logs.remove(logs.size() - 1);
        }
        System.out.println(logEntry);
    }

    public static List<String> getLogs() {
        return new ArrayList<>(logs);
    }
}
