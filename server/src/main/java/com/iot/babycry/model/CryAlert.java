package com.iot.babycry.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CryAlert {
    private String id;
    private LocalDateTime timestamp;
    private byte[] imageData;
    private String status;
}
