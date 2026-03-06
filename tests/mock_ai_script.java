import java.util.ArrayList;
import java.util.List;

public class TestAgent {
    public static void main(String[] args) {
        TestAgent agent = new TestAgent();
        List<String> list = new ArrayList<>();
        list.add("test");
        agent.run(list);
        System.out.println("Done");
    }

    public void run(List<String> data) {
        Processor proc = new Processor();
        proc.execute(data);
    }
}
