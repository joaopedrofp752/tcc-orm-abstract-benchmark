package cest.joaopedrofp.tcc_backend.model;

public class BenchmarkPayload {

    private Long id;
    private String name;
    private String description;
    private Double value;
    private Boolean active;

    public BenchmarkPayload() {
    }

    public BenchmarkPayload(Long id, String name, String description, Double value, Boolean active) {
        this.id = id;
        this.name = name;
        this.description = description;
        this.value = value;
        this.active = active;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public Double getValue() {
        return value;
    }

    public void setValue(Double value) {
        this.value = value;
    }

    public Boolean getActive() {
        return active;
    }

    public void setActive(Boolean active) {
        this.active = active;
    }
}
