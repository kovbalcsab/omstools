#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include <TFile.h>
#include <TLeaf.h>
#include <TTree.h>

namespace
{
   struct Options
   {
      std::string InputFileList;
      std::string OutputFile = "runlist.txt";
      int MaxFiles = -1;
   };

   std::string Trim(const std::string &Text)
   {
      std::size_t Begin = 0;
      while(Begin < Text.size() && std::isspace(static_cast<unsigned char>(Text[Begin])) != 0)
         ++Begin;

      std::size_t End = Text.size();
      while(End > Begin && std::isspace(static_cast<unsigned char>(Text[End - 1])) != 0)
         --End;

      return Text.substr(Begin, End - Begin);
   }

   bool StartsWith(const std::string &Text, const std::string &Prefix)
   {
      return Text.rfind(Prefix, 0) == 0;
   }

   void PrintUsage(const char *ProgramName)
   {
      std::cout
         << "Usage: " << ProgramName << " --input <filelist.txt> [--output runlist.txt] [--max-files N]\n"
         << "Options:\n"
         << "  --input <path>      Text file with one ROOT file path per line\n"
         << "  --output <path>     Output text file with one unique run number per line\n"
         << "  --max-files <N>     Optional limit on the number of input files to process\n"
         << "  --help              Show this help message\n";
   }

   Options ParseCommandLine(int argc, char *argv[])
   {
      Options Result;

      for(int i = 1; i < argc; ++i)
      {
         const std::string Argument = argv[i];

         if(Argument == "--help")
         {
            PrintUsage(argv[0]);
            std::exit(0);
         }
         if(Argument == "--input" && i + 1 < argc)
         {
            Result.InputFileList = argv[++i];
            continue;
         }
         if(Argument == "--output" && i + 1 < argc)
         {
            Result.OutputFile = argv[++i];
            continue;
         }
         if(Argument == "--max-files" && i + 1 < argc)
         {
            Result.MaxFiles = std::stoi(argv[++i]);
            continue;
         }

         throw std::runtime_error("unrecognized or incomplete argument: " + Argument);
      }

      if(Result.InputFileList.empty())
         throw std::runtime_error("missing required argument: --input");

      return Result;
   }

   std::string ResolveInputPath(const std::string &RawPath)
   {
      const std::string Path = Trim(RawPath);
      if(Path.empty())
         return "";

      if(StartsWith(Path, "/store/"))
         return "/eos/cms" + Path;

      return Path;
   }

   std::vector<std::string> ReadFileList(const std::string &FileListName, int MaxFiles)
   {
      std::ifstream Input(FileListName);
      if(Input.is_open() == false)
         throw std::runtime_error("failed to open file list: " + FileListName);

      std::vector<std::string> Files;
      std::string Line;
      while(std::getline(Input, Line))
      {
         const std::string Path = ResolveInputPath(Line);
         if(Path.empty() || StartsWith(Path, "#"))
            continue;

         Files.push_back(Path);
         if(MaxFiles > 0 && static_cast<int>(Files.size()) >= MaxFiles)
            break;
      }

      return Files;
   }

   std::set<long long> ReadRunsFromTree(const std::string &FileName)
   {
      std::unique_ptr<TFile> Input(TFile::Open(FileName.c_str(), "READ"));
      if(Input == nullptr || Input->IsZombie())
         throw std::runtime_error("failed to open ROOT file: " + FileName);

      TTree *Tree = dynamic_cast<TTree *>(Input->Get("hiEvtAnalyzer/HiTree"));
      if(Tree == nullptr)
         throw std::runtime_error("missing tree hiEvtAnalyzer/HiTree in file: " + FileName);

      Tree->SetBranchStatus("*", 0);
      Tree->SetBranchStatus("run", 1);

      TLeaf *RunLeaf = Tree->GetLeaf("run");
      if(RunLeaf == nullptr)
         throw std::runtime_error("missing branch run in tree hiEvtAnalyzer/HiTree for file: " + FileName);

      std::set<long long> Runs;
      const Long64_t EntryCount = Tree->GetEntries();
      for(Long64_t iE = 0; iE < EntryCount; ++iE)
      {
         Tree->GetEntry(iE);
         Runs.insert(RunLeaf->GetValueLong64());
      }

      return Runs;
   }

   void EnsureOutputDirectory(const std::string &OutputFileName)
   {
      const std::filesystem::path OutputPath(OutputFileName);
      if(OutputPath.has_parent_path())
         std::filesystem::create_directories(OutputPath.parent_path());
   }
}

int main(int argc, char *argv[])
{
   try
   {
      const Options Opt = ParseCommandLine(argc, argv);
      const std::vector<std::string> Files = ReadFileList(Opt.InputFileList, Opt.MaxFiles);

      if(Files.empty())
         throw std::runtime_error("no input ROOT files found in file list");

      std::set<long long> AllRuns;
      for(std::size_t iF = 0; iF < Files.size(); ++iF)
      {
         std::cout << "[" << (iF + 1) << "/" << Files.size() << "] " << Files[iF] << std::endl;
         const std::set<long long> FileRuns = ReadRunsFromTree(Files[iF]);
         AllRuns.insert(FileRuns.begin(), FileRuns.end());
      }

      EnsureOutputDirectory(Opt.OutputFile);
      std::ofstream Output(Opt.OutputFile);
      if(Output.is_open() == false)
         throw std::runtime_error("failed to open output file: " + Opt.OutputFile);

      for(const long long Run : AllRuns)
         Output << Run << "\n";

      std::cout << "Wrote " << AllRuns.size() << " unique runs to " << Opt.OutputFile << std::endl;
      return 0;
   }
   catch(const std::exception &Ex)
   {
      std::cerr << "error: " << Ex.what() << std::endl;
      return 1;
   }
}
