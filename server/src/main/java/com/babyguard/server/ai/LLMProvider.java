package com.babyguard.server.ai;

public interface LLMProvider {
    String call(ChatRequest request);
}
