// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract UserAuthentication {
    struct User {
        bytes32 passwordHash;
        bool exists;
        string username;
    }
    
    struct Document {
        string documentName;
        string photoCid;
        string description;
        string doctorName;
    }
    
    // Mappings to store user details
    mapping(string => User) private users; // User data stored under username (as string)
    mapping(string => Document[]) private userDocuments; // Documents stored under username
    mapping(string => bool) private documentCollections; // Track if a username has documents
    
    event UserRegistered(string username);
    event UserLoggedIn(string username);
    event DocumentUploaded(string username, string documentName, string doctorName);
    
    // Function to register a new user (doctor)
    function registerUser(string memory username, string memory password) public returns (bool) {
        require(!users[username].exists, "Username already taken");
        
        bytes32 passwordHash = keccak256(abi.encodePacked(password));
        users[username] = User(passwordHash, true, username);
        
        emit UserRegistered(username);
        return true;
    }
    
    // Function to login user (doctor)
    function login(string memory username, string memory password) public returns (bool) {
        require(users[username].exists, "User does not exist");
        
        bytes32 passwordHash = keccak256(abi.encodePacked(password));
        require(users[username].passwordHash == passwordHash, "Invalid password");
        
        emit UserLoggedIn(username);
        return true;
    }
    
    // Check if a user exists (only for doctors)
    function userExists(string memory username) public view returns (bool) {
        return users[username].exists;
    }
    
    // Add a document for a patient username reference
    function addDocument(
        string memory patientUsername,  // This is just a reference, doesn't need to exist
        string memory documentName,
        string memory photoCid,
        string memory description,
        string memory doctorName        // This should be a registered user
    ) public returns (bool) {
        // No check for patient username existence
        
        Document memory newDocument = Document(documentName, photoCid, description, doctorName);
        userDocuments[patientUsername].push(newDocument);
        documentCollections[patientUsername] = true; // Mark that this reference has documents
        
        emit DocumentUploaded(patientUsername, documentName, doctorName);
        return true;
    }
    
    // Check if a username reference has documents
    function hasDocuments(string memory patientUsername) public view returns (bool) {
        return documentCollections[patientUsername];
    }
    
    // Get all documents for a patient username reference
    function getDocuments(string memory patientUsername) public view returns (Document[] memory) {
        // No check for existence, just return the documents (can be empty array)
        return userDocuments[patientUsername];
    }
    
    // Get user details (for doctors)
    function getUserDetails(string memory username) public view returns (string memory) {
        require(users[username].exists, "User does not exist");
        return users[username].username;
    }
}