import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.*;
public class ReadOnly extends GhidraScript {
    public void run() throws Exception {
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) { b.setWrite(false); println("ro: "+b.getName()); }
    }
}
