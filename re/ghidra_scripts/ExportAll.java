import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class ExportAll extends GhidraScript {
    public void run() throws Exception {
        String out = getScriptArgs()[0];
        DecompInterface d = new DecompInterface();
        d.setOptions(new DecompileOptions());
        d.openProgram(currentProgram);
        PrintWriter c = new PrintWriter(new FileWriter(out + "/all.c"));
        PrintWriter a = new PrintWriter(new FileWriter(out + "/all.asm"));
        PrintWriter x = new PrintWriter(new FileWriter(out + "/xrefs.txt"));
        FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
        Listing lst = currentProgram.getListing();
        while (it.hasNext()) {
            Function f = it.next();
            c.println("// ===== " + f.getName() + " @ " + f.getEntryPoint() + " size=" + f.getBody().getNumAddresses());
            DecompileResults r = d.decompileFunction(f, 60, monitor);
            if (r != null && r.getDecompiledFunction() != null) c.println(r.getDecompiledFunction().getC());
            else c.println("// decompile failed");
            a.println("; ===== " + f.getName() + " @ " + f.getEntryPoint());
            InstructionIterator ii = lst.getInstructions(f.getBody(), true);
            while (ii.hasNext()) { Instruction in = ii.next(); a.println(in.getAddress() + "  " + in.toString()); }
            // callers
            ReferenceIterator ri = currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint());
            StringBuilder sb = new StringBuilder();
            while (ri.hasNext()) { Reference rf = ri.next(); Function cf = lst.getFunctionContaining(rf.getFromAddress()); sb.append(cf==null?rf.getFromAddress().toString():cf.getName()).append(" "); }
            x.println(f.getName() + " @ " + f.getEntryPoint() + " <- " + sb);
        }
        c.close(); a.close(); x.close();
        // data xrefs to RAM: dump every reference to 0x2000xxxx with the function that uses it
        PrintWriter m = new PrintWriter(new FileWriter(out + "/ram_refs.txt"));
        ReferenceManager rm = currentProgram.getReferenceManager();
        AddressIterator ai = rm.getReferenceDestinationIterator(toAddr(0x20000000), true);
        while (ai.hasNext()) {
            Address ad = ai.next();
            if (ad.getOffset() >= 0x20020000) break;
            StringBuilder sb = new StringBuilder();
            ReferenceIterator ri = rm.getReferencesTo(ad);
            while (ri.hasNext()) { Reference rf = ri.next(); Function cf = lst.getFunctionContaining(rf.getFromAddress()); sb.append(cf==null?"?":cf.getName()).append(rf.getReferenceType().isWrite()?"(W) ":rf.getReferenceType().isRead()?"(R) ":" "); }
            m.println(ad + " <- " + sb);
        }
        m.close();
    }
}
