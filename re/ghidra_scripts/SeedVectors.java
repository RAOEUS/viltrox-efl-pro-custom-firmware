import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.mem.*;
public class SeedVectors extends GhidraScript {
    void seed(long a) {
        try {
            if (a < 0x08020400L || a >= 0x0802E000L || (a & 1) == 0) return;
            Address ad = toAddr(a & ~1L);
            if (getFunctionAt(ad) != null) return;
            if (getInstructionAt(ad) == null) {
                Register tm = currentProgram.getProgramContext().getRegister("TMode");
                currentProgram.getProgramContext().setValue(tm, ad, ad, java.math.BigInteger.ONE);
                disassemble(ad);
            }
            createFunction(ad, null);
        } catch (Exception e) { }
    }
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        for (int i = 1; i < 101; i++) seed(mem.getInt(toAddr(0x08020400L + i*4)) & 0xffffffffL);
        for (long a = 0x08020400L; a < 0x0802D9C0L; a += 4) {
            long v = mem.getInt(toAddr(a)) & 0xffffffffL;
            if (v >= 0x08020400L && v < 0x0802D9C0L && (v & 1) == 1) seed(v);
        }
        println("seeded; functions=" + currentProgram.getFunctionManager().getFunctionCount());
    }
}
