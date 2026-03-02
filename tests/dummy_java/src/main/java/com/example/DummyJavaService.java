package com.example;

import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class DummyJavaService {

    private String serviceName;
    private int counter = 0;

    public DummyJavaService(String name) {
        this.serviceName = name;
    }

    public String getServiceName() {
        return this.serviceName;
    }

    public void processItems(List<String> items, boolean flag) {
        for (String item : items) {
            System.out.println("Processing: " + item);
        }
    }
    
    private void internalMethod() {
        this.counter++;
    }
}
