using System.Collections.Generic;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IGenreMappingDefaultsProvider
{
    IReadOnlyList<GenreMappingEntry> GetDefaultMappings();
}
